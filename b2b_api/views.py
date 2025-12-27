import os
import uuid
from decimal import Decimal, InvalidOperation

import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body, parse_limit_param
from services_common.tenancy import resolve_business_from_request
from services_common.status_codes import apply_mapped_status, map_status

from .models import B2BUSSDPushRequest, BulkBusinessPaymentBatch, BulkBusinessPaymentItem


def _serialize_batch(batch: BulkBusinessPaymentBatch):
    return {
        "id": str(batch.id),
        "business_id": str(batch.business_id) if getattr(batch, "business_id", None) else None,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "reference": batch.reference,
        "status": batch.status,
        "items_count": batch.items.count(),
        "meta": batch.meta,
        "last_error": batch.last_error,
    }


def _serialize_item(item: BulkBusinessPaymentItem):
    return {
        "id": item.id,
        "recipient": item.recipient,
        "amount": str(item.amount),
        "currency": item.currency,
        "product_type": item.product_type,
        "item_reference": item.item_reference,
        "status": item.status,
        "result": item.result,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_ussd_request(req: B2BUSSDPushRequest):
    return {
        "id": str(req.id),
        "business_id": str(req.business_id),
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        "environment": req.environment,
        "request_ref_id": req.request_ref_id,
        "response_code": req.response_code,
        "response_status": req.response_status,
        "status": req.status,
        "result_code": req.result_code,
        "result_desc": req.result_desc,
        "status_code": req.internal_status_code,
        "status_message": req.internal_status_message,
        "amount": req.amount,
        "product_type": req.product_type,
        "payment_reference": req.payment_reference,
        "conversation_id": req.conversation_id,
        "transaction_id": req.transaction_id,
        "callback_status": req.callback_status,
        "request_payload": req.request_payload,
        "api_response_payload": req.api_response_payload,
        "api_error_payload": req.api_error_payload,
        "callback_payload": req.callback_payload,
    }


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _get_b2b_ussd_url(environment: str) -> str:
    # Prefer explicit full URL from env for easy customization/deployment.
    full = _env("MPESA_B2B_USSD_API_URL", "")
    if full:
        return full

    base = _env("MPESA_B2B_USSD_API_BASE_URL", "")
    if base:
        return f"{base.rstrip('/')}/v1/ussdpush/get-msisdn"

    # Fallbacks (kept for convenience if env not set).
    if environment == "production":
        return "https://api.safaricom.co.ke/v1/ussdpush/get-msisdn"
    return "https://sandbox.safaricom.co.ke/v1/ussdpush/get-msisdn"


def _get_default_token_url(environment: str) -> str:
    base = _env("MPESA_DARAJA_API_BASE_URL", "")
    if base:
        return f"{base.rstrip('/')}/oauth/v1/generate?grant_type=client_credentials"
    if environment == "production":
        return "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    return "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"


def _get_daraja_credential(business_id, environment: str):
    from business_api.models import DarajaCredential

    cred = (
        DarajaCredential.objects.filter(
            business_id=business_id,
            is_active=True,
            environment=environment,
        )
        .order_by("-created_at")
        .first()
    )
    return cred


def _get_access_token(cred):
    token_url = (cred.token_url or "").strip() or _get_default_token_url(cred.environment)
    resp = requests.get(
        token_url,
        auth=(cred.consumer_key, cred.consumer_secret),
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"raw": (resp.text or "")}

    if resp.status_code < 200 or resp.status_code >= 300:
        raise RuntimeError(f"Token request failed ({resp.status_code}): {data}")

    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError(f"Token response missing access_token: {data}")
    return str(token)


@require_oauth2(scopes=["b2b:write"])
@csrf_exempt
def bulk_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    items = body.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return JsonResponse({"error": "items must be a non-empty list"}, status=400)

    reference = str(body.get("reference", "")).strip()[:64]
    business, error = resolve_business_from_request(request, body.get("business_id"))
    if error:
        return error

    meta = {k: v for k, v in body.items() if k not in {"items"}}
    batch = BulkBusinessPaymentBatch.objects.create(reference=reference, meta=meta, business=business)

    created = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        recipient = str(raw.get("recipient") or raw.get("party_b") or raw.get("account") or "").strip()
        amount_raw = raw.get("amount")
        currency = str(raw.get("currency") or "KES").strip().upper()[:3]
        product_type = str(raw.get("product_type") or "").strip()[:60]
        item_reference = str(raw.get("reference") or "").strip()[:64]

        if not recipient:
            continue
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError):
            continue
        if amount <= 0:
            continue

        BulkBusinessPaymentItem.objects.create(
            batch=batch,
            recipient=recipient,
            amount=amount,
            currency=currency or "KES",
            product_type=product_type,
            item_reference=item_reference,
        )
        created += 1

    if created == 0:
        batch.delete()
        return JsonResponse({"error": "No valid items provided"}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "batch": _serialize_batch(batch),
        },
        status=201,
    )


@require_staff
def bulk_list(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    limit = parse_limit_param(request, default=50, max_limit=200)

    qs = BulkBusinessPaymentBatch.objects.all()[:limit]
    return JsonResponse({"results": [_serialize_batch(b) for b in qs]})


@require_staff
def bulk_detail(request, batch_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        batch = BulkBusinessPaymentBatch.objects.get(id=batch_id)
    except BulkBusinessPaymentBatch.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    data = _serialize_batch(batch)
    data["items"] = [_serialize_item(i) for i in batch.items.all()]
    return JsonResponse(data)


@require_oauth2(scopes=["b2b:write"])
@csrf_exempt
def single_ussd_push(request):
    """Initiate a single USSD push request.

    External API (configurable): /v1/ussdpush/get-msisdn
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)

    business, error = resolve_business_from_request(request, body.get("business_id"))
    if error:
        return error

    environment = str(body.get("environment") or "sandbox").strip().lower()
    if environment not in {"sandbox", "production"}:
        return JsonResponse({"error": "environment must be sandbox or production"}, status=400)

    primary_short_code = str(body.get("primary_short_code") or body.get("primaryShortCode") or _env("MPESA_B2B_PRIMARY_SHORT_CODE", "")).strip()
    receiver_short_code = str(body.get("receiver_short_code") or body.get("receiverShortCode") or _env("MPESA_B2B_RECEIVER_SHORT_CODE", "")).strip()
    payment_ref = str(body.get("payment_ref") or body.get("paymentRef") or _env("MPESA_B2B_PAYMENT_REF", "paymentRef")).strip()
    callback_url = str(body.get("callback_url") or body.get("callbackUrl") or _env("MPESA_B2B_CALLBACK_URL", "")).strip()
    partner_name = str(body.get("partner_name") or body.get("partnerName") or _env("MPESA_B2B_PARTNER_NAME", "Vendor")).strip()

    if not primary_short_code or not receiver_short_code:
        return JsonResponse({"error": "primary_short_code and receiver_short_code are required"}, status=400)
    if not callback_url:
        return JsonResponse({"error": "callback_url is required (or set MPESA_B2B_CALLBACK_URL)"}, status=400)
    if not partner_name:
        return JsonResponse({"error": "partner_name is required"}, status=400)

    amount_raw = body.get("amount")
    try:
        amount_dec = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "amount must be a number"}, status=400)
    if amount_dec <= 0:
        return JsonResponse({"error": "amount must be > 0"}, status=400)
    amount_str = str(amount_dec)

    request_ref_id = str(body.get("request_ref_id") or body.get("RequestRefID") or "").strip()
    if not request_ref_id:
        request_ref_id = str(uuid.uuid4())

    payload = {
        "primaryShortCode": primary_short_code,
        "receiverShortCode": receiver_short_code,
        "amount": amount_str,
        "paymentRef": payment_ref,
        "callbackUrl": callback_url,
        "partnerName": partner_name,
        "RequestRefID": request_ref_id,
    }

    req = B2BUSSDPushRequest.objects.create(
        business=business,
        environment=environment,
        request_ref_id=request_ref_id,
        status=B2BUSSDPushRequest.STATUS_QUEUED,
        amount=amount_str,
        product_type=str(body.get("product_type") or "").strip()[:60],
        request_payload=payload,
    )

    try:
        cred = _get_daraja_credential(business.id, environment)
        if not cred:
            req.status = B2BUSSDPushRequest.STATUS_ERROR
            req.api_error_payload = {"error": f"No active DarajaCredential for business/environment ({environment})"}
            req.save(update_fields=["status", "api_error_payload", "updated_at"])
            return JsonResponse({"error": "Daraja credentials not configured for this business"}, status=400)

        token = _get_access_token(cred)

        url = _get_b2b_ussd_url(environment)
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": (resp.text or "")}

        if resp.status_code < 200 or resp.status_code >= 300:
            req.status = B2BUSSDPushRequest.STATUS_ERROR
            req.api_error_payload = data if isinstance(data, dict) else {"error": data}
            req.save(update_fields=["status", "api_error_payload", "updated_at"])
            return JsonResponse({"error": "Safaricom API error", "details": req.api_error_payload}, status=502)

        req.status = B2BUSSDPushRequest.STATUS_SUBMITTED
        req.api_response_payload = data if isinstance(data, dict) else {"data": data}
        if isinstance(data, dict):
            req.response_code = str(data.get("code") or "")
            req.response_status = str(data.get("status") or "")
        req.save(update_fields=["status", "api_response_payload", "response_code", "response_status", "updated_at"])

        mapped = map_status(
            external_system="safaricom",
            external_code=req.response_code,
            external_message=req.response_status,
        )
        return JsonResponse(
            {
                "ok": True,
                "status_code": mapped.status_code,
                "status_message": mapped.status_message,
                "ussd_request": _serialize_ussd_request(req),
            },
            status=201,
        )
    except Exception as e:
        req.status = B2BUSSDPushRequest.STATUS_ERROR
        req.api_error_payload = {"error": str(e)}
        req.save(update_fields=["status", "api_error_payload", "updated_at"])
        return JsonResponse({"error": "Failed to submit", "details": req.api_error_payload}, status=502)


@csrf_exempt
def callback_result(request):
    """USSD callback result (called by Safaricom)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    request_id = str(body.get("requestId") or body.get("RequestRefID") or "").strip()
    if not request_id:
        return JsonResponse({"error": "Missing requestId"}, status=400)

    try:
        req = B2BUSSDPushRequest.objects.get(request_ref_id=request_id)
    except B2BUSSDPushRequest.DoesNotExist:
        return JsonResponse({"error": "Unknown requestId"}, status=404)

    result_code = str(body.get("resultCode") or "").strip()
    result_desc = str(body.get("resultDesc") or "").strip()

    new_status = B2BUSSDPushRequest.STATUS_FAILED
    if result_code == "0":
        new_status = B2BUSSDPushRequest.STATUS_SUCCESS
    elif result_code == "4001":
        new_status = B2BUSSDPushRequest.STATUS_CANCELLED

    req.callback_payload = body
    req.status = new_status
    req.result_code = result_code
    req.result_desc = result_desc
    if result_code:
        apply_mapped_status(
            req,
            external_system="safaricom",
            external_code=result_code,
            external_message=result_desc,
        )
    req.amount = str(body.get("amount") or req.amount or "")
    req.payment_reference = str(body.get("paymentReference") or req.payment_reference or "")
    req.conversation_id = str(body.get("conversationID") or req.conversation_id or "")
    req.transaction_id = str(body.get("transactionId") or req.transaction_id or "")
    req.callback_status = str(body.get("status") or req.callback_status or "")
    req.save(
        update_fields=[
            "callback_payload",
            "status",
            "result_code",
            "result_desc",
            "internal_status_code",
            "internal_status_message",
            "amount",
            "payment_reference",
            "conversation_id",
            "transaction_id",
            "callback_status",
            "updated_at",
        ]
    )

    return JsonResponse({"ok": True})
