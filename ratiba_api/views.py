import os
import re

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from mpesa_api.mpesa_credentials import MpesaC2bCredential
from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body

from .models import RatibaOrder


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
    }
    if include_payloads:
        data["request_payload"] = order.request_payload
        data["response_payload"] = order.response_payload
    return data


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

    validation_error = _validate_ratiba_payload(payload)
    if validation_error:
        return JsonResponse({"error": validation_error}, status=400)

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        RatibaOrder.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            requested_by=_maybe_user(request),
            request_payload=payload,
            response_status=502,
            response_payload={},
            error=str(e),
        )
        return JsonResponse({"error": "Upstream request failed"}, status=502)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": (resp.text or "")}

    RatibaOrder.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        requested_by=_maybe_user(request),
        request_payload=payload,
        response_status=resp.status_code,
        response_payload=data if isinstance(data, dict) else {"data": data},
        error="" if resp.status_code < 400 else "Upstream returned an error",
    )

    return JsonResponse(data, status=resp.status_code)


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
