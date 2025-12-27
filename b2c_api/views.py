import os
import uuid
from decimal import Decimal, InvalidOperation

import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body, parse_limit_param
from services_common.tenancy import resolve_business_from_request
from services_common.status_codes import apply_mapped_status, map_safaricom_status

from .models import B2CPaymentRequest, BulkPayoutBatch, BulkPayoutItem


def _serialize_batch(batch: BulkPayoutBatch):
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


def _serialize_item(item: BulkPayoutItem):
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


def _serialize_payment_request(pr: B2CPaymentRequest):
    return {
        "id": str(pr.id),
        "business_id": str(pr.business_id),
        "bulk_item_id": pr.bulk_item_id,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
        "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
        "environment": pr.environment,
        "originator_conversation_id": pr.originator_conversation_id,
        "conversation_id": pr.conversation_id,
        "response_code": pr.response_code,
        "response_description": pr.response_description,
        "status": pr.status,
        "result_code": pr.result_code,
        "result_desc": pr.result_desc,
        "status_code": pr.internal_status_code,
        "status_message": pr.internal_status_message,
        "transaction_id": pr.transaction_id,
        "product_type": pr.product_type,
        "request_payload": pr.request_payload,
        "api_response_payload": pr.api_response_payload,
        "api_error_payload": pr.api_error_payload,
        "callback_result_payload": pr.callback_result_payload,
        "callback_timeout_payload": pr.callback_timeout_payload,
    }


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _get_paymentrequest_url(environment: str) -> str:
    base = _env("MPESA_B2C_API_BASE_URL", "")
    if base:
        return f"{base.rstrip('/')}/mpesa/b2c/v3/paymentrequest"
    if environment == "production":
        return "https://api.safaricom.co.ke/mpesa/b2c/v3/paymentrequest"
    return "https://sandbox.safaricom.co.ke/mpesa/b2c/v3/paymentrequest"


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


@require_oauth2(scopes=["b2c:write"])
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
    batch = BulkPayoutBatch.objects.create(reference=reference, meta=meta, business=business)

    created = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        recipient = str(raw.get("recipient") or raw.get("phone_number") or "").strip()
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

        BulkPayoutItem.objects.create(
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


@require_oauth2(scopes=["b2c:write"])
@csrf_exempt
def single_paymentrequest(request):
    """Initiate a single Safaricom B2C v3 paymentrequest.

    Expected body (minimal):
    - business_id
    - party_b (recipient MSISDN)
    - amount

    Optional:
    - environment: sandbox|production
    - party_a, command_id, remarks, queue_timeout_url, result_url, occasion
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

    party_b = str(body.get("party_b") or body.get("recipient") or "").strip()
    if not party_b:
        return JsonResponse({"error": "party_b is required"}, status=400)

    amount_raw = body.get("amount")
    try:
        amount_dec = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "amount must be a number"}, status=400)
    if amount_dec <= 0:
        return JsonResponse({"error": "amount must be > 0"}, status=400)
    amount = int(amount_dec)

    party_a = str(body.get("party_a") or _env("MPESA_B2C_PARTY_A", "")).strip()
    if not party_a:
        # Try first active shortcode as a convenience
        try:
            shortcode = business.shortcodes.filter(is_active=True).order_by("-created_at").first()
            party_a = shortcode.shortcode if shortcode else ""
        except Exception:
            party_a = ""
    if not party_a:
        return JsonResponse({"error": "party_a is required (or set MPESA_B2C_PARTY_A)"}, status=400)

    initiator_name = str(body.get("initiator_name") or _env("MPESA_B2C_INITIATOR_NAME", "")).strip()
    security_credential = str(body.get("security_credential") or _env("MPESA_B2C_SECURITY_CREDENTIAL", "")).strip()
    if not initiator_name or not security_credential:
        return JsonResponse(
            {
                "error": "initiator_name and security_credential are required (or set MPESA_B2C_INITIATOR_NAME / MPESA_B2C_SECURITY_CREDENTIAL)",
            },
            status=400,
        )

    queue_timeout_url = str(body.get("queue_timeout_url") or _env("MPESA_B2C_QUEUE_TIMEOUT_URL", "")).strip()
    result_url = str(body.get("result_url") or _env("MPESA_B2C_RESULT_URL", "")).strip()
    if not queue_timeout_url or not result_url:
        return JsonResponse(
            {
                "error": "queue_timeout_url and result_url are required (or set MPESA_B2C_QUEUE_TIMEOUT_URL / MPESA_B2C_RESULT_URL)",
            },
            status=400,
        )

    command_id = str(body.get("command_id") or _env("MPESA_B2C_COMMAND_ID", "BusinessPayment")).strip()
    remarks = str(body.get("remarks") or body.get("Remarks") or "").strip()[:200]
    occasion = str(body.get("occasion") or body.get("Occassion") or "").strip()[:200]

    originator_conversation_id = str(body.get("originator_conversation_id") or "").strip()
    if not originator_conversation_id:
        originator_conversation_id = str(uuid.uuid4())

    payment_payload = {
        "OriginatorConversationID": originator_conversation_id,
        "InitiatorName": initiator_name,
        "SecurityCredential": security_credential,
        "CommandID": command_id,
        "Amount": amount,
        "PartyA": party_a,
        "PartyB": party_b,
        "Remarks": remarks,
        "QueueTimeOutURL": queue_timeout_url,
        "ResultURL": result_url,
        "Occassion": occasion,
    }

    pr = B2CPaymentRequest.objects.create(
        business=business,
        environment=environment,
        originator_conversation_id=originator_conversation_id,
        status=B2CPaymentRequest.STATUS_QUEUED,
        request_payload=payment_payload,
        product_type=str(body.get("product_type") or "").strip()[:60],
    )

    try:
        cred = _get_daraja_credential(business.id, environment)
        if not cred:
            pr.status = B2CPaymentRequest.STATUS_ERROR
            pr.api_error_payload = {"error": f"No active DarajaCredential for business/environment ({environment})"}
            pr.save(update_fields=["status", "api_error_payload", "updated_at"])
            return JsonResponse({"error": "Daraja credentials not configured for this business"}, status=400)

        token = _get_access_token(cred)

        payment_url = _get_paymentrequest_url(environment)
        resp = requests.post(
            payment_url,
            json=payment_payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": (resp.text or "")}

        if resp.status_code < 200 or resp.status_code >= 300:
            pr.status = B2CPaymentRequest.STATUS_ERROR
            pr.api_error_payload = data if isinstance(data, dict) else {"error": data}
            pr.save(update_fields=["status", "api_error_payload", "updated_at"])
            return JsonResponse({"error": "Safaricom API error", "details": pr.api_error_payload}, status=502)

        pr.status = B2CPaymentRequest.STATUS_SUBMITTED
        pr.api_response_payload = data if isinstance(data, dict) else {"data": data}
        if isinstance(data, dict):
            pr.conversation_id = str(data.get("ConversationID") or "")
            pr.response_code = str(data.get("ResponseCode") or "")
            pr.response_description = str(data.get("ResponseDescription") or "")
        pr.save(
            update_fields=[
                "status",
                "api_response_payload",
                "conversation_id",
                "response_code",
                "response_description",
                "updated_at",
            ]
        )

        mapped = map_safaricom_status(code=pr.response_code, message=pr.response_description)
        return JsonResponse(
            {
                "ok": True,
                "status_code": mapped.status_code,
                "status_message": mapped.status_message,
                "payment_request": _serialize_payment_request(pr),
            },
            status=201,
        )
    except Exception as e:
        pr.status = B2CPaymentRequest.STATUS_ERROR
        pr.api_error_payload = {"error": str(e)}
        pr.save(update_fields=["status", "api_error_payload", "updated_at"])
        return JsonResponse({"error": "Failed to submit", "details": pr.api_error_payload}, status=502)


def _extract_originator_conversation_id(payload: dict) -> str:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("OriginatorConversationID"):
        return str(result.get("OriginatorConversationID") or "").strip()
    # Some integrations send top-level keys.
    if payload.get("OriginatorConversationID"):
        return str(payload.get("OriginatorConversationID") or "").strip()
    return ""


def _extract_transaction_id(payload: dict) -> str:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("TransactionID"):
        return str(result.get("TransactionID") or "").strip()
    return ""


@csrf_exempt
def callback_result(request):
    """ResultURL callback for B2C paymentrequest."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    originator_id = _extract_originator_conversation_id(body)
    if not originator_id:
        return JsonResponse({"error": "Missing OriginatorConversationID"}, status=400)

    try:
        pr = B2CPaymentRequest.objects.get(originator_conversation_id=originator_id)
    except B2CPaymentRequest.DoesNotExist:
        return JsonResponse({"error": "Unknown OriginatorConversationID"}, status=404)

    result = body.get("Result") if isinstance(body.get("Result"), dict) else {}
    pr.callback_result_payload = body
    pr.status = B2CPaymentRequest.STATUS_RESULT
    pr.conversation_id = str(result.get("ConversationID") or pr.conversation_id or "")
    pr.result_code = result.get("ResultCode") if isinstance(result.get("ResultCode"), int) else pr.result_code
    pr.result_desc = str(result.get("ResultDesc") or pr.result_desc or "")
    if pr.result_code is not None:
        apply_mapped_status(
            pr,
            external_system="safaricom",
            external_code=pr.result_code,
            external_message=pr.result_desc,
        )
    pr.transaction_id = _extract_transaction_id(body) or pr.transaction_id
    pr.save(
        update_fields=[
            "callback_result_payload",
            "status",
            "conversation_id",
            "result_code",
            "result_desc",
            "internal_status_code",
            "internal_status_message",
            "transaction_id",
            "updated_at",
        ]
    )

    if pr.bulk_item_id:
        try:
            item = BulkPayoutItem.objects.get(id=pr.bulk_item_id)
            item.result = body
            if pr.result_code == 0:
                item.status = "completed"
            else:
                item.status = "failed"
            item.save(update_fields=["result", "status", "updated_at"])
        except Exception:
            pass

    return JsonResponse({"ok": True})


@csrf_exempt
def callback_timeout(request):
    """QueueTimeOutURL callback for B2C paymentrequest."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    originator_id = _extract_originator_conversation_id(body)
    if not originator_id:
        return JsonResponse({"error": "Missing OriginatorConversationID"}, status=400)

    try:
        pr = B2CPaymentRequest.objects.get(originator_conversation_id=originator_id)
    except B2CPaymentRequest.DoesNotExist:
        return JsonResponse({"error": "Unknown OriginatorConversationID"}, status=404)

    pr.callback_timeout_payload = body
    pr.status = B2CPaymentRequest.STATUS_TIMEOUT
    pr.save(update_fields=["callback_timeout_payload", "status", "updated_at"])

    if pr.bulk_item_id:
        try:
            item = BulkPayoutItem.objects.get(id=pr.bulk_item_id)
            item.result = body
            item.status = "timeout"
            item.save(update_fields=["result", "status", "updated_at"])
        except Exception:
            pass

    return JsonResponse({"ok": True})


@require_staff
def single_list(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    limit = parse_limit_param(request, default=50, max_limit=200)
    qs = B2CPaymentRequest.objects.all()

    business_id = (request.GET.get("business_id") or "").strip()
    if business_id:
        qs = qs.filter(business_id=business_id)

    qs = qs[:limit]
    return JsonResponse({"results": [_serialize_payment_request(pr) for pr in qs]})


@require_staff
def single_detail(request, payment_request_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        pr = B2CPaymentRequest.objects.get(id=payment_request_id)
    except B2CPaymentRequest.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse(_serialize_payment_request(pr))


@require_staff
def bulk_list(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        limit = int(request.GET.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    qs = BulkPayoutBatch.objects.all()[:limit]
    return JsonResponse({"results": [_serialize_batch(b) for b in qs]})


@require_staff
def bulk_detail(request, batch_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        batch = BulkPayoutBatch.objects.get(id=batch_id)
    except BulkPayoutBatch.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    data = _serialize_batch(batch)
    data["items"] = [_serialize_item(i) for i in batch.items.all()]
    return JsonResponse(data)
