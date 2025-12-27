import os
import re
import uuid

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from mpesa_api.mpesa_credentials import MpesaC2bCredential
from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body
from services_common.status_codes import apply_mapped_status

from .models import RatibaOrder


def _resolve_shortcode(shortcode: str | None):
    if not shortcode:
        return None
    try:
        from business_api.models import MpesaShortcode

        return MpesaShortcode.objects.select_related("business").filter(shortcode=str(shortcode)).first()
    except Exception:
        return None


def _get_bound_business(request):
    token_obj = getattr(request, "oauth2_token", None)
    app = getattr(request, "oauth2_application", None) if token_obj else None
    if app is None:
        return None
    try:
        from business_api.models import OAuthClientBusiness

        binding = OAuthClientBusiness.objects.select_related("business").filter(application=app).first()
        return binding.business if binding else None
    except Exception:
        return None


def _get_default_shortcode_for_business(business):
    if not business:
        return None
    try:
        return business.shortcodes.filter(is_active=True).order_by("-created_at").first()
    except Exception:
        return None


def _maybe_user(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def _serialize_order(order: RatibaOrder, include_payloads: bool = False):
    data = {
        "id": str(order.id),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "response_status": order.response_status,
        "error": order.error or "",
        "callback_received_at": order.callback_received_at.isoformat() if order.callback_received_at else None,
        "callback_result_code": order.callback_result_code,
        "callback_result_description": order.callback_result_description or "",
        "status_code": order.internal_status_code,
        "status_message": order.internal_status_message or "",
    }
    if include_payloads:
        data["request_payload"] = order.request_payload
        data["response_payload"] = order.response_payload
        data["callback_payload"] = order.callback_payload
    return data


def _extract_account_reference(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("AccountReference", "accountReference", "account_reference"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_result_code(payload: dict):
    if not isinstance(payload, dict):
        return None
    for key in ("ResultCode", "resultCode", "result_code"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _extract_result_desc(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("ResultDesc", "ResultDescription", "resultDesc", "resultDescription", "result_desc"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


_DATE_YYYYMMDD_RE = re.compile(r"^\d{8}$")


def _validate_ratiba_payload(payload: dict) -> str | None:
    required = [
        "StandingOrderName",
        "StartDate",
        "EndDate",
        "BusinessShortCode",
        "TransactionType",
        "ReceiverPartyIdentifierType",
        "Amount",
        "PartyA",
        "CallBackURL",
        "AccountReference",
        "TransactionDesc",
        "Frequency",
    ]

    missing = [k for k in required if not str(payload.get(k, "")).strip()]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"

    if not _DATE_YYYYMMDD_RE.match(str(payload.get("StartDate"))):
        return "StartDate must be in YYYYMMDD format"
    if not _DATE_YYYYMMDD_RE.match(str(payload.get("EndDate"))):
        return "EndDate must be in YYYYMMDD format"

    if not str(payload.get("BusinessShortCode")).isdigit():
        return "BusinessShortCode must be numeric"

    amount_raw = str(payload.get("Amount")).strip()
    try:
        amount = float(amount_raw)
    except ValueError:
        return "Amount must be numeric"
    if amount <= 0:
        return "Amount must be greater than 0"

    party_a = str(payload.get("PartyA")).strip()
    if not party_a.isdigit() or len(party_a) < 10:
        return "PartyA must be a numeric MSISDN (e.g. 2547XXXXXXXX)"

    callback_url = str(payload.get("CallBackURL")).strip()
    if not (callback_url.startswith("https://") or callback_url.startswith("http://")):
        return "CallBackURL must be a valid URL"

    receiver_type = str(payload.get("ReceiverPartyIdentifierType")).strip()
    if not receiver_type.isdigit():
        return "ReceiverPartyIdentifierType must be numeric"

    frequency = str(payload.get("Frequency")).strip()
    if not frequency.isdigit():
        return "Frequency must be numeric"

    return None


@require_oauth2(scopes=["ratiba:write"])
@csrf_exempt
def create_ratiba(request):
    """Create an M-Pesa Ratiba standing order via Daraja.

    Upstream URL is read from env: `MPESA_RATIBA_URL`.

    Payload is passed through as JSON to the upstream API (Daraja validates).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_url = os.getenv("MPESA_RATIBA_URL")
    if not api_url:
        return JsonResponse({"error": "MPESA_RATIBA_URL is not set"}, status=500)

    access_token = MpesaC2bCredential.get_access_token()
    if not access_token:
        return JsonResponse({"error": "Failed to retrieve access token"}, status=500)

    payload = json_body(request)
    if not isinstance(payload, dict) or not payload:
        return JsonResponse({"error": "Request body must be a non-empty JSON object"}, status=400)

    # Normalize common alias keys to Daraja canonical keys.
    payload = dict(payload)
    if payload.get("CallBackURL") in (None, ""):
        alias = payload.get("callback_url") or payload.get("call_back_url") or payload.get("CallbackURL")
        if alias not in (None, ""):
            payload["CallBackURL"] = alias

    # Resolve tenancy context when possible.
    shortcode_value = str(payload.get("shortcode") or payload.get("business_shortcode") or payload.get("BusinessShortCode") or "").strip()
    shortcode_obj = _resolve_shortcode(shortcode_value)
    business = shortcode_obj.business if shortcode_obj else _get_bound_business(request)
    if not shortcode_obj and business:
        shortcode_obj = _get_default_shortcode_for_business(business)

    if payload.get("BusinessShortCode") in (None, "") and shortcode_obj:
        payload["BusinessShortCode"] = str(shortcode_obj.shortcode)

    if payload.get("CallBackURL") in (None, ""):
        default_cb = ""
        if shortcode_obj and getattr(shortcode_obj, "default_ratiba_callback_url", ""):
            default_cb = str(shortcode_obj.default_ratiba_callback_url or "")
        if not default_cb:
            default_cb = str(os.getenv("RATIBA_CALLBACK_URL") or "")
        if default_cb:
            payload["CallBackURL"] = default_cb

    validation_error = _validate_ratiba_payload(payload)
    if validation_error:
        return JsonResponse({"error": validation_error}, status=400)

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        RatibaOrder.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            requested_by=_maybe_user(request),
            business=business,
            shortcode=shortcode_obj,
            request_payload=payload,
            response_status=502,
            response_payload={},
            error=str(e),
        )
        return JsonResponse({"error": "Upstream request failed"}, status=502)

    try:
        data = resp.json()
    except ValueError:
        data = {"raw": (resp.text or "")}

    RatibaOrder.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        requested_by=_maybe_user(request),
        business=business,
        shortcode=shortcode_obj,
        request_payload=payload,
        response_status=resp.status_code,
        response_payload=data if isinstance(data, dict) else {"data": data},
        error="" if resp.status_code < 400 else "Upstream returned an error",
    )

    return JsonResponse(data, status=resp.status_code)


@csrf_exempt
def ratiba_callback(request):
    """Receive Ratiba standing order callback from M-Pesa.

    This endpoint is intentionally unauthenticated/CSRF-exempt so Safaricom can reach it.
    It updates the most relevant `RatibaOrder` record when possible.

    Matching strategy:
    - If query param `order_id=<uuid>` is present, update that order.
    - Else, try to match by `AccountReference` in the callback payload.
    """

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    matched_order = None

    raw_order_id = str(request.GET.get("order_id") or "").strip()
    if raw_order_id:
        try:
            order_uuid = uuid.UUID(raw_order_id)
            matched_order = RatibaOrder.objects.filter(id=order_uuid).first()
        except ValueError:
            matched_order = None

    if matched_order is None:
        account_ref = _extract_account_reference(payload)
        if account_ref:
            matched_order = (
                RatibaOrder.objects.filter(request_payload__AccountReference=account_ref)
                .order_by("-created_at")
                .first()
            )

    result_code = _extract_result_code(payload)
    result_desc = _extract_result_desc(payload)

    if matched_order is None:
        RatibaOrder.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            requested_by=_maybe_user(request),
            request_payload={},
            response_status=None,
            response_payload={},
            callback_received_at=timezone.now(),
            callback_result_code=result_code,
            callback_result_description=result_desc,
            callback_payload=payload,
            error="Unmatched Ratiba callback (no related order found)",
        )
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"}, status=200)

    matched_order.callback_received_at = timezone.now()
    matched_order.callback_result_code = result_code
    matched_order.callback_result_description = result_desc
    matched_order.callback_payload = payload
    if result_code is not None:
        apply_mapped_status(
            matched_order,
            external_system="safaricom",
            external_code=result_code,
            external_message=result_desc,
        )
    matched_order.save(
        update_fields=[
            "callback_received_at",
            "callback_result_code",
            "callback_result_description",
            "internal_status_code",
            "internal_status_message",
            "callback_payload",
            "updated_at",
        ]
    )

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"}, status=200)


@require_staff
def ratiba_history(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    items = RatibaOrder.objects.all()[:50]
    return JsonResponse({"results": [_serialize_order(i) for i in items]}, status=200)


@require_staff
def ratiba_detail(request, order_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    order = get_object_or_404(RatibaOrder, id=order_id)
    return JsonResponse(_serialize_order(order, include_payloads=True), status=200)
