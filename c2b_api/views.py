"""C2B service endpoints.

This module owns the C2B/STK endpoints under `/api/v1/c2b/*`.

Legacy routes under `mpesa_api` remain supported via thin wrappers.
"""

import datetime
import json
import os

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from requests.auth import HTTPBasicAuth

from mpesa_api.models import MpesaCallBacks, MpesaCalls, MpesaPayment
from mpesa_api.mpesa_credentials import LipanaMpesaPassword, MpesaC2bCredential
from services_common.auth import require_internal_api_key
from services_common.http import json_body, parse_mpesa_timestamp


@require_internal_api_key
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
@require_internal_api_key
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

        password, timestamp = LipanaMpesaPassword.generate_password()
        body = json_body(request)

        payload = {
            "BusinessShortCode": LipanaMpesaPassword.BUSINESS_SHORT_CODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": body.get("amount", 1),
            "PartyA": body.get("party_a") or os.getenv("PARTY_A"),
            "PartyB": LipanaMpesaPassword.BUSINESS_SHORT_CODE,
            "PhoneNumber": body.get("phone_number") or os.getenv("PHONE_NUMBER"),
            "CallBackURL": os.getenv("STK_CALLBACK_URL", ""),
            "AccountReference": os.getenv("ACCOUNT_REFERENCE"),
            "TransactionDesc": "Testing STK push",
        }

        if not payload.get("CallBackURL"):
            return JsonResponse({"error": "STK_CALLBACK_URL is not set"}, status=500)

        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Request",
            conversation_id=payload.get("AccountReference", ""),
            content=json.dumps(payload),
        )

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"error": "Invalid JSON response", "status_code": response.status_code}

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_internal_api_key
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

        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="Confirmation Callback",
            conversation_id=mpesa_body.get("TransID", ""),
            content=json.dumps(mpesa_body),
        )

        MpesaPayment.objects.create(
            transaction_id=mpesa_body.get("TransID"),
            amount=mpesa_body.get("TransAmount", 0),
            transaction_date=parse_mpesa_timestamp(mpesa_body.get("TransTime")),
            phone_number=mpesa_body.get("MSISDN"),
            status="successful",
            result_code=0,
            result_description="C2B Confirmation",
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

        MpesaPayment.objects.create(
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_description=result_desc,
            amount=amount,
            mpesa_receipt_number=mpesa_receipt_number,
            transaction_date=transaction_date,
            phone_number=phone_number,
            status=status,
        )

        MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Callback",
            conversation_id=merchant_request_id,
            content=stk_callback_data,
            result_code=result_code,
            result_description=result_desc,
        )

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

        MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Error",
            conversation_id=merchant_request_id,
            content=error_data,
            result_code=result_code,
            result_description=result_desc,
        )

        return JsonResponse({"status": "error received"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_internal_api_key(message="Please sign in with a staff account to view transactions.")
def transactions_completed(request):
    """Fetch completed M-Pesa transactions with optional filters."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        date_filter = request.GET.get("date", None)
        status_filter = request.GET.get("status", None)

        transactions = MpesaPayment.objects.all()

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


@require_internal_api_key(message="Please sign in with a staff account to view transactions.")
def transactions_all(request):
    """Fetch all M-Pesa transactions."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        transactions = MpesaPayment.objects.all()
        return JsonResponse({"transactions": list(transactions.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

