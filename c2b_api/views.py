"""C2B service endpoints.

This module owns the C2B/STK endpoints under `/api/v1/c2b/*`.

Legacy routes under `mpesa_api` remain supported via thin wrappers.
"""

import datetime
import json
import os
import uuid
from decimal import Decimal, InvalidOperation

import requests
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from requests.auth import HTTPBasicAuth
from django.utils import timezone

from mpesa_api.models import MpesaCallBacks, MpesaCalls, MpesaPayment, StkPushInitiation, MpesaTransactionStatusQuery
from mpesa_api.mpesa_credentials import LipanaMpesaPassword, MpesaC2bCredential
from services_common.auth import require_oauth2, require_staff
from services_common.http import json_body, parse_mpesa_timestamp
from services_common.tenancy import resolve_business_from_request
from services_common.status_codes import apply_mapped_status, map_safaricom_status


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
    if not app:
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


def _extract_originator_conversation_id(payload: dict) -> str:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("OriginatorConversationID"):
        return str(result.get("OriginatorConversationID") or "").strip()
    if payload.get("OriginatorConversationID"):
        return str(payload.get("OriginatorConversationID") or "").strip()
    return ""


def _extract_conversation_id(payload: dict) -> str:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("ConversationID"):
        return str(result.get("ConversationID") or "").strip()
    if payload.get("ConversationID"):
        return str(payload.get("ConversationID") or "").strip()
    return ""


def _extract_transaction_id(payload: dict) -> str:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("TransactionID"):
        return str(result.get("TransactionID") or "").strip()
    return ""


def _extract_result_parameters(payload: dict) -> dict[str, str]:
    result = payload.get("Result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return {}

    params = result.get("ResultParameters")
    if not isinstance(params, dict):
        return {}

    items = params.get("ResultParameter")
    if not isinstance(items, list):
        return {}

    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("Key") or "").strip()
        if not key:
            continue
        out[key] = str(item.get("Value") or "").strip()
    return out


@require_staff
def get_access_token(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")
    api_url = os.getenv("TOKEN_URL")

    if not consumer_key or not consumer_secret or not api_url:
        return JsonResponse({"error": "Missing required credentials in environment"}, status=500)

    r = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret), timeout=30)
    try:
        mpesa_access_token = r.json()
    except Exception:
        mpesa_access_token = {}

    validated = mpesa_access_token.get("access_token")
    if validated:
        return JsonResponse({"access_token": validated})
    return JsonResponse({"error": "Failed to retrieve access token"}, status=500)


@csrf_exempt
@require_oauth2(scopes=["c2b:write"])
def stk_push(request):
    """Initiates Lipa Na Mpesa Online Payment (STK Push)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("LIPA_NA_MPESA_ONLINE_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        if not access_token or not api_url:
            return JsonResponse(
                {"error": "Missing access token or LIPA_NA_MPESA_ONLINE_URL"},
                status=500,
            )

        body = json_body(request)

        shortcode_value = str(body.get("shortcode") or body.get("business_shortcode") or "").strip()
        shortcode_obj = _resolve_shortcode(shortcode_value)

        # Backward compatible fallback to env-based config if shortcode not provided.
        effective_shortcode = shortcode_obj.shortcode if shortcode_obj else LipanaMpesaPassword.BUSINESS_SHORT_CODE
        effective_passkey = shortcode_obj.lipa_passkey if shortcode_obj else None
        password, timestamp = LipanaMpesaPassword.generate_password(
            business_shortcode=effective_shortcode,
            passkey=effective_passkey,
        )

        callback_url = (
            str(body.get("callback_url") or "").strip()
            or (shortcode_obj.default_stk_callback_url if shortcode_obj else "")
            or os.getenv("STK_CALLBACK_URL", "")
        )
        account_reference = str(body.get("account_reference") or "").strip()[:64] or os.getenv("ACCOUNT_REFERENCE")
        product_type = str(body.get("product_type") or "").strip()[:60]

        payload = {
            "BusinessShortCode": effective_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": body.get("amount", 1),
            "PartyA": body.get("party_a") or os.getenv("PARTY_A"),
            "PartyB": effective_shortcode,
            "PhoneNumber": body.get("phone_number") or os.getenv("PHONE_NUMBER"),
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": "Testing STK push",
        }

        if not payload.get("CallBackURL"):
            return JsonResponse({"error": "STK_CALLBACK_URL is not set"}, status=500)

        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Request",
            conversation_id=payload.get("AccountReference", ""),
            content=json.dumps(payload),
            business=shortcode_obj.business if shortcode_obj else None,
            shortcode=shortcode_obj,
        )

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"error": "Invalid JSON response", "status_code": response.status_code}

        # Persist mapping for tenancy resolution on callback.
        if isinstance(response_data, dict):
            merchant_request_id = response_data.get("MerchantRequestID")
            checkout_request_id = response_data.get("CheckoutRequestID")
            if merchant_request_id or checkout_request_id:
                StkPushInitiation.objects.create(
                    business=shortcode_obj.business if shortcode_obj else None,
                    shortcode=shortcode_obj,
                    merchant_request_id=merchant_request_id,
                    checkout_request_id=checkout_request_id,
                    account_reference=account_reference or "",
                    product_type=product_type,
                    request_payload=payload,
                    response_payload=response_data,
                )

        # Integrator-facing response: include our simplified mapped status.
        if isinstance(response_data, dict):
            mapped = map_safaricom_status(
                code=response_data.get("ResponseCode") or response_data.get("responseCode"),
                message=response_data.get("ResponseDescription") or response_data.get("responseDescription"),
            )
            response_data = {
                **response_data,
                "status_code": mapped.status_code,
                "status_message": mapped.status_message,
            }

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_oauth2(
    scopes=["transactions:write"],
    message="Please sign in with a staff account to reconcile transactions.",
)
def transaction_status_query(request):
    """Initiate Safaricom Transaction Status Query for a known transaction id.

    This is primarily used for reconciliation when callbacks are delayed.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    transaction_id = str(body.get("transaction_id") or body.get("TransID") or body.get("mpesa_receipt_number") or "").strip()
    if not transaction_id:
        return JsonResponse({"error": "transaction_id is required"}, status=400)

    shortcode_value = str(body.get("shortcode") or body.get("business_shortcode") or "").strip()
    shortcode_obj = _resolve_shortcode(shortcode_value)
    if not shortcode_obj:
        bound_business = _get_bound_business(request)
        shortcode_obj = _get_default_shortcode_for_business(bound_business)

    api_url = str(os.getenv("MPESA_TXN_STATUS_QUERY_URL") or "").strip()
    if not api_url:
        return JsonResponse({"error": "MPESA_TXN_STATUS_QUERY_URL is not set"}, status=500)

    initiator_name = str(body.get("initiator_name") or "").strip() or str(
        (getattr(shortcode_obj, "txn_status_initiator_name", "") if shortcode_obj else "")
    ).strip() or str(os.getenv("MPESA_TXN_STATUS_INITIATOR_NAME") or "").strip()
    security_credential = str(body.get("security_credential") or "").strip() or str(
        (getattr(shortcode_obj, "txn_status_security_credential", "") if shortcode_obj else "")
    ).strip() or str(os.getenv("MPESA_TXN_STATUS_SECURITY_CREDENTIAL") or "").strip()
    if not initiator_name or not security_credential:
        return JsonResponse(
            {
                "error": "initiator_name and security_credential are required (or set MPESA_TXN_STATUS_INITIATOR_NAME / MPESA_TXN_STATUS_SECURITY_CREDENTIAL)",
            },
            status=400,
        )

    result_url = str(body.get("result_url") or "").strip() or str(
        (getattr(shortcode_obj, "txn_status_result_url", "") if shortcode_obj else "")
    ).strip() or str(os.getenv("MPESA_TXN_STATUS_RESULT_URL") or "").strip()
    timeout_url = str(body.get("queue_timeout_url") or body.get("timeout_url") or "").strip() or str(
        (getattr(shortcode_obj, "txn_status_timeout_url", "") if shortcode_obj else "")
    ).strip() or str(os.getenv("MPESA_TXN_STATUS_TIMEOUT_URL") or "").strip()
    if not result_url or not timeout_url:
        return JsonResponse(
            {
                "error": "result_url and timeout_url are required (or set MPESA_TXN_STATUS_RESULT_URL / MPESA_TXN_STATUS_TIMEOUT_URL)",
            },
            status=400,
        )

    party_a = str(body.get("party_a") or os.getenv("MPESA_TXN_STATUS_PARTY_A") or "").strip()
    if not party_a and shortcode_obj:
        party_a = str(shortcode_obj.shortcode)
    if not party_a:
        return JsonResponse({"error": "party_a is required (or set MPESA_TXN_STATUS_PARTY_A)"}, status=400)

    identifier_type = str(body.get("identifier_type") or "").strip() or str(
        (getattr(shortcode_obj, "txn_status_identifier_type", "") if shortcode_obj else "")
    ).strip() or str(os.getenv("MPESA_TXN_STATUS_IDENTIFIER_TYPE") or "4").strip()
    remarks = str(body.get("remarks") or "Reconcile transaction").strip()[:200]
    occasion = str(body.get("occasion") or "").strip()[:200]

    originator_conversation_id = str(body.get("originator_conversation_id") or "").strip() or str(uuid.uuid4())

    payload = {
        "Initiator": initiator_name,
        "SecurityCredential": security_credential,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id,
        "PartyA": party_a,
        "IdentifierType": identifier_type,
        "ResultURL": result_url,
        "QueueTimeOutURL": timeout_url,
        "Remarks": remarks,
        "Occasion": occasion,
        "OriginatorConversationID": originator_conversation_id,
    }

    row = MpesaTransactionStatusQuery.objects.create(
        business=shortcode_obj.business if shortcode_obj else None,
        shortcode=shortcode_obj,
        transaction_id=transaction_id,
        originator_conversation_id=originator_conversation_id,
        request_payload=payload,
        status="pending",
    )

    try:
        access_token = MpesaC2bCredential.get_access_token()
        if not access_token:
            row.response_payload = {"error": "Failed to get access token"}
            row.status = "failed"
            row.save(update_fields=["response_payload", "status", "updated_at"])
            return JsonResponse({"error": "Failed to get access token"}, status=502)

        resp = requests.post(
            api_url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": (resp.text or ""), "status_code": resp.status_code}

        row.response_payload = data if isinstance(data, dict) else {"data": data}
        if isinstance(data, dict):
            row.conversation_id = str(data.get("ConversationID") or row.conversation_id or "")
            row.originator_conversation_id = str(data.get("OriginatorConversationID") or row.originator_conversation_id or "")
        row.save(update_fields=["response_payload", "conversation_id", "originator_conversation_id", "updated_at"])

        mapped = None
        if isinstance(row.response_payload, dict):
            mapped = map_safaricom_status(
                code=row.response_payload.get("ResponseCode") or row.response_payload.get("responseCode"),
                message=row.response_payload.get("ResponseDescription")
                or row.response_payload.get("responseDescription"),
            )

        return JsonResponse(
            {
                "ok": True,
                "query_id": row.id,
                "status_code": mapped.status_code if mapped else None,
                "status_message": mapped.status_message if mapped else "",
                "response": row.response_payload,
            },
            status=201,
        )
    except Exception as e:
        row.response_payload = {"error": str(e)}
        row.status = "failed"
        row.save(update_fields=["response_payload", "status", "updated_at"])
        return JsonResponse({"error": "Failed to submit", "details": row.response_payload}, status=502)


@csrf_exempt
def transaction_status_result(request):
    """ResultURL callback for Transaction Status Query."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    originator_id = _extract_originator_conversation_id(body)
    conversation_id = _extract_conversation_id(body)
    result = body.get("Result") if isinstance(body.get("Result"), dict) else {}
    result_code = result.get("ResultCode") if isinstance(result.get("ResultCode"), int) else None
    result_desc = str(result.get("ResultDesc") or "").strip()

    cb = MpesaCallBacks.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        caller="Transaction Status Result",
        conversation_id=originator_id or conversation_id,
        content=body,
        result_code=result_code,
        result_description=result_desc,
    )

    if result_code is not None:
        apply_mapped_status(
            cb,
            external_system="safaricom",
            external_code=result_code,
            external_message=result_desc,
            code_field="internal_status_code",
            message_field="internal_status_message",
        )
        cb.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])

    row = None
    if originator_id:
        row = MpesaTransactionStatusQuery.objects.filter(originator_conversation_id=originator_id).first()
    if not row and conversation_id:
        row = MpesaTransactionStatusQuery.objects.filter(conversation_id=conversation_id).first()

    txn_id = ""
    if row and row.transaction_id:
        txn_id = str(row.transaction_id or "").strip()
    if not txn_id:
        txn_id = _extract_transaction_id(body)
    if not txn_id:
        params = _extract_result_parameters(body)
        txn_id = params.get("ReceiptNo") or params.get("TransactionID") or ""
    txn_id = str(txn_id or "").strip()

    if row:
        row.result_payload = body
        row.result_code = result_code
        row.result_description = result_desc
        if result_code is not None:
            apply_mapped_status(
                row,
                external_system="safaricom",
                external_code=result_code,
                external_message=result_desc,
            )
        row.resolved_at = timezone.now()
        if txn_id and not row.transaction_id:
            row.transaction_id = txn_id
        if isinstance(result_code, int):
            row.status = "successful" if result_code == 0 else "failed"
        row.save(
            update_fields=[
                "result_payload",
                "result_code",
                "result_description",
                "internal_status_code",
                "internal_status_message",
                "resolved_at",
                "transaction_id",
                "status",
                "updated_at",
            ]
        )

    if txn_id:
        payments = MpesaPayment.objects.filter(models.Q(transaction_id=txn_id) | models.Q(mpesa_receipt_number=txn_id))
        for p in payments:
            if (p.status or "").lower() == "pending":
                p.status = "successful" if result_code == 0 else "failed"
                p.result_code = result_code
                p.result_description = result_desc
                if result_code is not None:
                    apply_mapped_status(
                        p,
                        external_system="safaricom",
                        external_code=result_code,
                        external_message=result_desc,
                    )
                    p.save(
                        update_fields=[
                            "status",
                            "result_code",
                            "result_description",
                            "internal_status_code",
                            "internal_status_message",
                            "updated_at",
                        ]
                    )
                else:
                    p.save(update_fields=["status", "result_code", "result_description", "updated_at"])

    return JsonResponse({"ok": True})


@csrf_exempt
def transaction_status_timeout(request):
    """QueueTimeOutURL callback for Transaction Status Query."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    originator_id = _extract_originator_conversation_id(body)
    conversation_id = _extract_conversation_id(body)
    cb = MpesaCallBacks.objects.create(
        ip_address=request.META.get("REMOTE_ADDR"),
        caller="Transaction Status Timeout",
        conversation_id=originator_id or conversation_id,
        content=body,
        result_code=-1,
        result_description="timeout",
    )

    apply_mapped_status(
        cb,
        external_system="gateway",
        external_code="TIMEOUT",
        external_message="timeout",
        code_field="internal_status_code",
        message_field="internal_status_message",
    )
    cb.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])

    row = None
    if originator_id:
        row = MpesaTransactionStatusQuery.objects.filter(originator_conversation_id=originator_id).first()
    if not row and conversation_id:
        row = MpesaTransactionStatusQuery.objects.filter(conversation_id=conversation_id).first()

    if row:
        row.result_payload = body
        row.result_code = -1
        row.result_description = "timeout"
        apply_mapped_status(
            row,
            external_system="gateway",
            external_code="TIMEOUT",
            external_message="timeout",
        )
        row.resolved_at = timezone.now()
        row.save(
            update_fields=[
                "result_payload",
                "result_code",
                "result_description",
                "internal_status_code",
                "internal_status_message",
                "resolved_at",
                "updated_at",
            ]
        )

    return JsonResponse({"ok": True})


@csrf_exempt
@require_staff
def register_urls(request):
    """Registers Mpesa Confirmation and Validation URLs."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("REGISTER_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        confirmation_url = os.getenv("CONFIRMATION_URL")
        validation_url = os.getenv("VALIDATION_URL")

        if not api_url or not confirmation_url or not validation_url:
            return JsonResponse({"error": "One or more required URLs are missing in .env"}, status=500)

        c2b_shortcode = os.getenv("C2B_SHORTCODE") or LipanaMpesaPassword.BUSINESS_SHORT_CODE
        payload = {
            "ShortCode": c2b_shortcode,
            "ResponseType": "Completed",
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url,
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"error": "Invalid JSON response", "status_code": response.status_code}

        if isinstance(response_data, dict):
            error_message = str(response_data.get("errorMessage", ""))
            if "Duplicate notification info" in error_message:
                response_data = {
                    **response_data,
                    "note": "Notification URLs already registered for this shortcode.",
                }
                return JsonResponse(response_data, status=200)

        return JsonResponse(response_data, status=response.status_code)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def validation(request):
    """Handles validation callback."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
def confirmation(request):
    """Handles confirmation callback and saves transaction details."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        mpesa_body = json_body(request)

        shortcode_obj = _resolve_shortcode(mpesa_body.get("BusinessShortCode") or mpesa_body.get("ShortCode"))

        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="Confirmation Callback",
            conversation_id=mpesa_body.get("TransID", ""),
            content=json.dumps(mpesa_body),
            business=shortcode_obj.business if shortcode_obj else None,
            shortcode=shortcode_obj,
        )

        trans_id = str(mpesa_body.get("TransID") or "").strip()
        if not trans_id:
            return JsonResponse({"error": "Missing TransID"}, status=400)

        desired_status = "successful"
        latest_status = (
            MpesaTransactionStatusQuery.objects.filter(transaction_id=trans_id)
            .exclude(status="pending")
            .order_by("-created_at")
            .first()
        )
        if latest_status and latest_status.status in {"successful", "failed"}:
            desired_status = latest_status.status

        payment = MpesaPayment.objects.filter(transaction_id=trans_id).first()
        if payment:
            # Don't override a final status (e.g. already reconciled).
            if (payment.status or "").lower() not in {"successful", "failed"}:
                payment.status = desired_status
                payment.result_code = 0
                payment.result_description = "C2B Confirmation"

            payment.amount = mpesa_body.get("TransAmount", payment.amount or 0)
            payment.transaction_date = parse_mpesa_timestamp(mpesa_body.get("TransTime")) or payment.transaction_date
            payment.phone_number = mpesa_body.get("MSISDN") or payment.phone_number
            if not payment.business_id and shortcode_obj:
                payment.business = shortcode_obj.business
            if not payment.shortcode_id and shortcode_obj:
                payment.shortcode = shortcode_obj
            payment.save(
                update_fields=[
                    "amount",
                    "transaction_date",
                    "phone_number",
                    "status",
                    "result_code",
                    "result_description",
                    "business",
                    "shortcode",
                    "updated_at",
                ]
            )
        else:
            MpesaPayment.objects.create(
                transaction_id=trans_id,
                amount=mpesa_body.get("TransAmount", 0),
                transaction_date=parse_mpesa_timestamp(mpesa_body.get("TransTime")),
                phone_number=mpesa_body.get("MSISDN"),
                status=desired_status,
                result_code=0,
                result_description="C2B Confirmation",
                business=shortcode_obj.business if shortcode_obj else None,
                shortcode=shortcode_obj,
            )

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def stk_callback(request):
    """Handles STK Push callback from M-Pesa (Success or Failure)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        raw = json_body(request)
        stk_callback_data = raw.get("Body", {}).get("stkCallback") if isinstance(raw, dict) else None
        if not stk_callback_data:
            stk_callback_data = raw

        merchant_request_id = stk_callback_data.get("MerchantRequestID", "")
        checkout_request_id = stk_callback_data.get("CheckoutRequestID", "")
        result_code = stk_callback_data.get("ResultCode", None)
        result_desc = stk_callback_data.get("ResultDesc", "")

        callback_metadata = stk_callback_data.get("CallbackMetadata", {}).get("Item", [])
        transaction_data = {
            item.get("Name"): item.get("Value")
            for item in callback_metadata
            if isinstance(item, dict) and item.get("Name")
        }

        mpesa_receipt_number = transaction_data.get("MpesaReceiptNumber", "")
        amount = transaction_data.get("Amount", 0)
        transaction_date = transaction_data.get("TransactionDate", None)
        phone_number = transaction_data.get("PhoneNumber", "")

        transaction_date = parse_mpesa_timestamp(transaction_date)
        status = "successful" if result_code == 0 else "failed"

        initiation = None
        if checkout_request_id:
            initiation = (
                StkPushInitiation.objects.select_related("business", "shortcode")
                .filter(checkout_request_id=checkout_request_id)
                .first()
            )

        desired_status = status
        txn_id = str(mpesa_receipt_number or "").strip()
        if txn_id:
            latest_status = (
                MpesaTransactionStatusQuery.objects.filter(transaction_id=txn_id)
                .exclude(status="pending")
                .order_by("-created_at")
                .first()
            )
            if latest_status and latest_status.status in {"successful", "failed"}:
                desired_status = latest_status.status

        payment = None
        if checkout_request_id:
            payment = MpesaPayment.objects.filter(checkout_request_id=checkout_request_id).first()
        if not payment and merchant_request_id:
            payment = MpesaPayment.objects.filter(merchant_request_id=merchant_request_id).first()

        if payment:
            if (payment.status or "").lower() not in {"successful", "failed"}:
                payment.status = desired_status
                payment.result_code = result_code
                payment.result_description = result_desc
                apply_mapped_status(
                    payment,
                    external_system="safaricom",
                    external_code=result_code,
                    external_message=result_desc,
                )
            payment.merchant_request_id = merchant_request_id or payment.merchant_request_id
            payment.checkout_request_id = checkout_request_id or payment.checkout_request_id
            payment.amount = amount or payment.amount
            payment.mpesa_receipt_number = txn_id or payment.mpesa_receipt_number
            if txn_id and not payment.transaction_id:
                payment.transaction_id = txn_id
            payment.transaction_date = transaction_date or payment.transaction_date
            payment.phone_number = phone_number or payment.phone_number
            if not payment.business_id and initiation:
                payment.business = initiation.business
            if not payment.shortcode_id and initiation:
                payment.shortcode = initiation.shortcode
            if not (payment.product_type or "").strip() and initiation:
                payment.product_type = str(initiation.product_type or "").strip()[:60]
            payment.save(
                update_fields=[
                    "merchant_request_id",
                    "checkout_request_id",
                    "transaction_id",
                    "product_type",
                    "amount",
                    "mpesa_receipt_number",
                    "transaction_date",
                    "phone_number",
                    "status",
                    "result_code",
                    "result_description",
                    "internal_status_code",
                    "internal_status_message",
                    "business",
                    "shortcode",
                    "updated_at",
                ]
            )
        else:
            payment = MpesaPayment.objects.create(
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id,
                transaction_id=txn_id or None,
                product_type=str(initiation.product_type or "").strip()[:60] if initiation else "",
                result_code=result_code,
                result_description=result_desc,
                amount=amount,
                mpesa_receipt_number=txn_id,
                transaction_date=transaction_date,
                phone_number=phone_number,
                status=desired_status,
                business=initiation.business if initiation else None,
                shortcode=initiation.shortcode if initiation else None,
            )
            apply_mapped_status(
                payment,
                external_system="safaricom",
                external_code=result_code,
                external_message=result_desc,
            )
            payment.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])

        cb = MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Callback",
            conversation_id=merchant_request_id,
            content=stk_callback_data,
            result_code=result_code,
            result_description=result_desc,
            business=initiation.business if initiation else None,
            shortcode=initiation.shortcode if initiation else None,
        )

        apply_mapped_status(
            cb,
            external_system="safaricom",
            external_code=result_code,
            external_message=result_desc,
            code_field="internal_status_code",
            message_field="internal_status_message",
        )
        cb.save(update_fields=["internal_status_code", "internal_status_message", "updated_at"])

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Received Successfully"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def stk_error(request):
    """Handles STK Push errors (e.g., invalid request, insufficient funds)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        error_data = json_body(request)

        merchant_request_id = error_data.get("MerchantRequestID", "")
        result_code = error_data.get("ResultCode", "")
        result_desc = error_data.get("ResultDesc", "")

        initiation = None
        if merchant_request_id:
            initiation = (
                StkPushInitiation.objects.select_related("business", "shortcode")
                .filter(merchant_request_id=merchant_request_id)
                .first()
            )

        MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Error",
            conversation_id=merchant_request_id,
            content=error_data,
            result_code=result_code,
            result_description=result_desc,
            business=initiation.business if initiation else None,
            shortcode=initiation.shortcode if initiation else None,
        )

        return JsonResponse({"status": "error received"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_oauth2(scopes=["transactions:read"], message="Please sign in with a staff account to view transactions.")
def transactions_completed(request):
    """Fetch completed M-Pesa transactions with optional filters."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        date_filter = request.GET.get("date", None)
        status_filter = request.GET.get("status", None)

        transactions = MpesaPayment.objects.all()

        business_id = request.GET.get("business_id")
        if business_id:
            transactions = transactions.filter(business_id=business_id)

        if date_filter:
            try:
                date_obj = datetime.datetime.strptime(date_filter, "%d/%m/%Y").date()
                transactions = transactions.filter(transaction_date__date=date_obj)
            except ValueError:
                return JsonResponse({"error": "Invalid date format. Use dd/mm/yyyy."}, status=400)

        if status_filter:
            status_filter = str(status_filter).lower()
            if status_filter in ["failed", "successful"]:
                transactions = transactions.filter(status__iexact=status_filter)
            else:
                return JsonResponse({"error": "Invalid status. Use 'failed' or 'successful'."}, status=400)
        else:
            transactions = transactions.filter(status="successful")

        return JsonResponse({"transactions": list(transactions.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_oauth2(scopes=["transactions:read"], message="Please sign in with a staff account to view transactions.")
def transactions_all(request):
    """Fetch all M-Pesa transactions."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        transactions = MpesaPayment.objects.all()

        token_obj = getattr(request, "oauth2_token", None)
        if token_obj is not None:
            business, error = resolve_business_from_request(request, request.GET.get("business_id"))
            if error:
                return error
            transactions = transactions.filter(business=business)
        else:
            business_id = request.GET.get("business_id")
            if business_id:
                transactions = transactions.filter(business_id=business_id)
        return JsonResponse({"transactions": list(transactions.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_oauth2(scopes=["transactions:read"], message="Please sign in with a staff account to view transactions.")
def transactions_aggregate(request):
    """Aggregate transactions by product type.

    OAuth callers are scoped to their bound business; staff can optionally filter by business_id.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        token_obj = getattr(request, "oauth2_token", None)
        provided_business_id = request.GET.get("business_id")

        business = None
        if token_obj is not None or provided_business_id:
            business, error = resolve_business_from_request(request, provided_business_id)
            if error:
                return error

        def _pt(value: str) -> str:
            return str(value or "").strip()[:60]

        def _add(bucket: dict[str, dict[str, Decimal]], product_type: str, key: str, amount: Decimal):
            pt = _pt(product_type)
            if pt not in bucket:
                bucket[pt] = {"c2b_incoming": Decimal("0"), "b2c_outgoing": Decimal("0"), "b2b_outgoing": Decimal("0")}
            bucket[pt][key] = bucket[pt][key] + amount

        by_product: dict[str, dict[str, Decimal]] = {}

        # C2B / STK incoming
        qs_c2b = MpesaPayment.objects.filter(status__iexact="successful")
        if business is not None:
            qs_c2b = qs_c2b.filter(business=business)
        for p in qs_c2b.only("product_type", "amount"):
            try:
                amt = Decimal(str(p.amount or 0))
            except (InvalidOperation, TypeError):
                continue
            _add(by_product, getattr(p, "product_type", ""), "c2b_incoming", amt)

        # B2C outgoing (single requests)
        from b2c_api.models import B2CPaymentRequest, BulkPayoutItem

        qs_b2c = B2CPaymentRequest.objects.filter(status=B2CPaymentRequest.STATUS_RESULT, result_code=0)
        if business is not None:
            qs_b2c = qs_b2c.filter(business=business)
        for pr in qs_b2c.only("product_type", "request_payload"):
            payload = pr.request_payload if isinstance(pr.request_payload, dict) else {}
            amount_raw = payload.get("Amount")
            try:
                amt = Decimal(str(amount_raw or 0))
            except (InvalidOperation, TypeError):
                continue
            _add(by_product, getattr(pr, "product_type", ""), "b2c_outgoing", amt)

        # B2C outgoing (bulk items marked completed)
        qs_b2c_items = BulkPayoutItem.objects.filter(status="completed")
        if business is not None:
            qs_b2c_items = qs_b2c_items.filter(batch__business=business)
        for item in qs_b2c_items.select_related("batch").only("product_type", "amount"):
            try:
                amt = Decimal(str(item.amount or 0))
            except (InvalidOperation, TypeError):
                continue
            _add(by_product, getattr(item, "product_type", ""), "b2c_outgoing", amt)

        # B2B outgoing (single USSD push requests)
        from b2b_api.models import B2BUSSDPushRequest, BulkBusinessPaymentItem

        qs_b2b = B2BUSSDPushRequest.objects.filter(status=B2BUSSDPushRequest.STATUS_SUCCESS)
        if business is not None:
            qs_b2b = qs_b2b.filter(business=business)
        for req in qs_b2b.only("product_type", "amount", "request_payload"):
            amount_raw = req.amount
            if not str(amount_raw or "").strip():
                payload = req.request_payload if isinstance(req.request_payload, dict) else {}
                amount_raw = payload.get("amount")
            try:
                amt = Decimal(str(amount_raw or 0))
            except (InvalidOperation, TypeError):
                continue
            _add(by_product, getattr(req, "product_type", ""), "b2b_outgoing", amt)

        # B2B outgoing (bulk items marked completed)
        qs_b2b_items = BulkBusinessPaymentItem.objects.filter(status="completed")
        if business is not None:
            qs_b2b_items = qs_b2b_items.filter(batch__business=business)
        for item in qs_b2b_items.select_related("batch").only("product_type", "amount"):
            try:
                amt = Decimal(str(item.amount or 0))
            except (InvalidOperation, TypeError):
                continue
            _add(by_product, getattr(item, "product_type", ""), "b2b_outgoing", amt)

        # Totals
        totals = {"c2b_incoming": Decimal("0"), "b2c_outgoing": Decimal("0"), "b2b_outgoing": Decimal("0")}
        for _, row in by_product.items():
            totals["c2b_incoming"] += row["c2b_incoming"]
            totals["b2c_outgoing"] += row["b2c_outgoing"]
            totals["b2b_outgoing"] += row["b2b_outgoing"]

        resp = {
            "business_id": str(business.id) if business is not None else None,
            "totals": {
                "c2b_incoming": str(totals["c2b_incoming"]),
                "b2c_outgoing": str(totals["b2c_outgoing"]),
                "b2b_outgoing": str(totals["b2b_outgoing"]),
                "net": str(totals["c2b_incoming"] - totals["b2c_outgoing"] - totals["b2b_outgoing"]),
            },
            "by_product_type": {
                pt: {
                    "c2b_incoming": str(v["c2b_incoming"]),
                    "b2c_outgoing": str(v["b2c_outgoing"]),
                    "b2b_outgoing": str(v["b2b_outgoing"]),
                    "net": str(v["c2b_incoming"] - v["b2c_outgoing"] - v["b2b_outgoing"]),
                }
                for pt, v in sorted(by_product.items(), key=lambda kv: kv[0])
            },
        }
        return JsonResponse(resp)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

