import json
import os

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from mpesa_api.models import MpesaCalls
from mpesa_api.mpesa_credentials import MpesaC2bCredential
from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body
from services_common.status_codes import apply_mapped_status

from .models import QrCode


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


def _maybe_user_id(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def _serialize_qr(record: QrCode, include_payloads: bool = False):
    data = {
        "id": str(record.id),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "merchant_name": record.merchant_name,
        "ref_no": record.ref_no,
        "amount": str(record.amount),
        "trx_code": record.trx_code,
        "cpi": record.cpi,
        "size": record.size,
        "response_status": record.response_status,
        "has_qr_code": bool(record.qr_code_base64),
        "error": record.error or "",
        "status_code": record.internal_status_code,
        "status_message": record.internal_status_message or "",
    }
    if include_payloads:
        data["request_payload"] = record.request_payload
        data["response_payload"] = record.response_payload
        data["qr_code_base64"] = record.qr_code_base64
    return data


@require_oauth2(scopes=["qr:write"])
@csrf_exempt
def generate_qr(request):
    """Generate an M-Pesa QR code via Daraja QR API.

    Expects JSON body:
      - MerchantName (string)
      - RefNo (string)
      - Amount (number)
      - TrxCode (string)
      - CPI (string) (optional)
      - Size (string|number) (optional)

    Upstream URL is read from env: `MPESA_QR_CODE_URL`.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_url = os.getenv("MPESA_QR_CODE_URL")
    if not api_url:
        return JsonResponse({"error": "MPESA_QR_CODE_URL is not set"}, status=500)

    access_token = MpesaC2bCredential.get_access_token()
    if not access_token:
        return JsonResponse({"error": "Failed to retrieve access token"}, status=500)

    body = json_body(request)
    if not isinstance(body, dict):
        body = {}

    # Resolve tenancy context when possible.
    shortcode_value = str(body.get("shortcode") or body.get("business_shortcode") or "").strip()
    shortcode_obj = _resolve_shortcode(shortcode_value)
    business = shortcode_obj.business if shortcode_obj else _get_bound_business(request)
    if not shortcode_obj and business:
        shortcode_obj = _get_default_shortcode_for_business(business)

    # Accept either canonical Daraja keys or snake_case aliases from the dashboard.
    payload = {
        "MerchantName": body.get("MerchantName") or body.get("merchant_name") or (business.name if business else ""),
        "RefNo": body.get("RefNo") or body.get("ref_no") or "",
        "Amount": body.get("Amount") if body.get("Amount") is not None else body.get("amount"),
        "TrxCode": body.get("TrxCode") or body.get("trx_code") or "",
    }

    cpi = body.get("CPI") if body.get("CPI") is not None else body.get("cpi")
    size = body.get("Size") if body.get("Size") is not None else body.get("size")
    if cpi in (None, "") and shortcode_obj:
        cpi = str(shortcode_obj.shortcode)
    if cpi not in (None, ""):
        payload["CPI"] = cpi
    if size not in (None, ""):
        payload["Size"] = size

    # Basic validation (keep it minimal).
    if not str(payload.get("MerchantName") or "").strip():
        return JsonResponse({"error": "MerchantName is required"}, status=400)
    if not str(payload.get("RefNo") or "").strip():
        return JsonResponse({"error": "RefNo is required"}, status=400)
    if payload.get("Amount") in (None, ""):
        return JsonResponse({"error": "Amount is required"}, status=400)
    if not str(payload.get("TrxCode") or "").strip():
        return JsonResponse({"error": "TrxCode is required"}, status=400)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    MpesaCalls.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        caller="QR Generate Request",
        conversation_id=str(payload.get("RefNo") or ""),
        content=json.dumps(payload),
    )

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        rec = QrCode.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            requested_by=_maybe_user_id(request),
            business=business,
            shortcode=shortcode_obj,
            merchant_name=str(payload.get("MerchantName") or ""),
            ref_no=str(payload.get("RefNo") or ""),
            amount=payload.get("Amount") or 0,
            trx_code=str(payload.get("TrxCode") or ""),
            cpi=str(payload.get("CPI") or ""),
            size=str(payload.get("Size") or ""),
            request_payload=payload,
            response_status=502,
            response_payload={},
            error=str(e),
        )
        apply_mapped_status(
            rec,
            external_system="gateway",
            external_code="REQUEST_ERROR",
            external_message=str(e),
        )
        rec.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])
        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="QR Generate Error",
            conversation_id=str(payload.get("RefNo") or ""),
            content=json.dumps({"error": str(e)}),
        )
        return JsonResponse(
            {
                "error": str(e),
                "status_code": rec.internal_status_code,
                "status_message": rec.internal_status_message or str(e),
            },
            status=502,
        )

    try:
        data = resp.json()
    except Exception:
        data = {"raw": (resp.text or "")}

    MpesaCalls.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        caller="QR Generate Response",
        conversation_id=str(payload.get("RefNo") or ""),
        content=json.dumps({"status": resp.status_code, "data": data}),
    )

    qr_base64 = ""
    if isinstance(data, dict) and isinstance(data.get("QRCode"), str):
        qr_base64 = data.get("QRCode") or ""

    rec = QrCode.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        requested_by=_maybe_user_id(request),
        business=business,
        shortcode=shortcode_obj,
        merchant_name=str(payload.get("MerchantName") or ""),
        ref_no=str(payload.get("RefNo") or ""),
        amount=payload.get("Amount") or 0,
        trx_code=str(payload.get("TrxCode") or ""),
        cpi=str(payload.get("CPI") or ""),
        size=str(payload.get("Size") or ""),
        request_payload=payload,
        response_status=resp.status_code,
        response_payload=data if isinstance(data, dict) else {"data": data},
        qr_code_base64=qr_base64,
    )

    response_code = None
    response_desc = ""
    if isinstance(data, dict):
        response_code = data.get("ResponseCode") or data.get("responseCode")
        response_desc = str(data.get("ResponseDescription") or data.get("responseDescription") or "").strip()

    if response_code is not None and str(response_code).strip() != "":
        mapped = apply_mapped_status(
            rec,
            external_system="safaricom",
            external_code=response_code,
            external_message=response_desc,
        )
    else:
        mapped = apply_mapped_status(
            rec,
            external_system="gateway",
            external_code=f"HTTP_{resp.status_code}",
            external_message=response_desc,
        )

    rec.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])

    if isinstance(data, dict):
        data["status_code"] = mapped.status_code
        data["status_message"] = mapped.status_message

    return JsonResponse(data, status=resp.status_code)


@require_staff
def qr_history(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    items = QrCode.objects.all()[:50]
    return JsonResponse({"results": [_serialize_qr(r) for r in items]}, status=200)


@require_staff
def qr_detail(request, qr_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    record = get_object_or_404(QrCode, id=qr_id)
    return JsonResponse(_serialize_qr(record, include_payloads=True), status=200)
