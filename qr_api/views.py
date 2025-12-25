import json
import os

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from mpesa_api.models import MpesaCalls
from mpesa_api.mpesa_credentials import MpesaC2bCredential
from services_common.auth import require_internal_api_key
from services_common.http import json_body

from .models import QrCode


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
    }
    if include_payloads:
        data["request_payload"] = record.request_payload
        data["response_payload"] = record.response_payload
        data["qr_code_base64"] = record.qr_code_base64
    return data


@require_internal_api_key
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

    # Accept either canonical Daraja keys or snake_case aliases from the dashboard.
    payload = {
        "MerchantName": body.get("MerchantName") or body.get("merchant_name") or "",
        "RefNo": body.get("RefNo") or body.get("ref_no") or "",
        "Amount": body.get("Amount") if body.get("Amount") is not None else body.get("amount"),
        "TrxCode": body.get("TrxCode") or body.get("trx_code") or "",
    }

    cpi = body.get("CPI") if body.get("CPI") is not None else body.get("cpi")
    size = body.get("Size") if body.get("Size") is not None else body.get("size")
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
        QrCode.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            requested_by=_maybe_user_id(request),
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
        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="QR Generate Error",
            conversation_id=str(payload.get("RefNo") or ""),
            content=json.dumps({"error": str(e)}),
        )
        return JsonResponse({"error": str(e)}, status=502)

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

    QrCode.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        requested_by=_maybe_user_id(request),
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

    return JsonResponse(data, status=resp.status_code)


@require_internal_api_key
def qr_history(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    items = QrCode.objects.all()[:50]
    return JsonResponse({"results": [_serialize_qr(r) for r in items]}, status=200)


@require_internal_api_key
def qr_detail(request, qr_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    record = get_object_or_404(QrCode, id=qr_id)
    return JsonResponse(_serialize_qr(record, include_payloads=True), status=200)
