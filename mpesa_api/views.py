from django.http import JsonResponse
import requests
from requests.auth import HTTPBasicAuth
import json
from django.views.decorators.csrf import csrf_exempt
import datetime
from dotenv import load_dotenv
import os

from .mpesa_credentials import MpesaC2bCredential, LipanaMpesaPassword
from .models import MpesaPayment, MpesaCallBacks, MpesaCalls
from django.utils import timezone
from functools import wraps

load_dotenv()


def _parse_mpesa_timestamp(value):
    if not value:
        return None
    try:
        value_str = str(value)
        # Common M-Pesa timestamp format: YYYYMMDDHHMMSS
        if len(value_str) == 14 and value_str.isdigit():
            dt = datetime.datetime.strptime(value_str, "%Y%m%d%H%M%S")
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
    except Exception:
        return None
    return None


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _get_provided_api_key(request):
    # Prefer standard custom header
    provided = request.headers.get("X-API-Key")
    if provided:
        return provided.strip()

    # Allow Authorization: Bearer <key> for convenience
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return ""


def require_internal_api_key(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        required = os.getenv("INTERNAL_API_KEY")
        if not required:
            return JsonResponse({"error": "INTERNAL_API_KEY is not set"}, status=500)

        provided = _get_provided_api_key(request)
        if not provided:
            return JsonResponse({"error": "Missing API key"}, status=401)
        if provided != required:
            return JsonResponse({"error": "Invalid API key"}, status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped

@require_internal_api_key
def get_access_token(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    consumer_key = os.getenv('CONSUMER_KEY')
    consumer_secret = os.getenv('CONSUMER_SECRET')
    api_URL = os.getenv('TOKEN_URL')

    if not consumer_key or not consumer_secret or not api_URL:
        return JsonResponse({"error": "Missing required credentials in environment"}, status=500)

    r = requests.get(api_URL, auth=HTTPBasicAuth(consumer_key, consumer_secret), timeout=30)
    try:
        mpesa_access_token = r.json()
    except Exception:
        mpesa_access_token = {}

    validated_mpesa_access_token = mpesa_access_token.get('access_token')

    if validated_mpesa_access_token:
        return JsonResponse({"access_token": validated_mpesa_access_token})
    else:
        return JsonResponse({"error": "Failed to retrieve access token"}, status=500)

@csrf_exempt
@require_internal_api_key
def lipa_na_mpesa_online(request):
    """Initiates Lipa Na Mpesa Online Payment (STK Push)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("LIPA_NA_MPESA_ONLINE_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        if not access_token or not api_url:
            return JsonResponse({"error": "Missing access token or LIPA_NA_MPESA_ONLINE_URL"}, status=500)

        password, timestamp = LipanaMpesaPassword.generate_password()

        body = _json_body(request)

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
            "TransactionDesc": "Testing STK push"
        }

        if not payload.get("CallBackURL"):
            return JsonResponse({"error": "STK_CALLBACK_URL is not set"}, status=500)

        # Log the outgoing request
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
    """Registers Mpesa Confirmation and Validation URLs"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("REGISTER_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        # Fetch URLs from env
        confirmation_url = os.getenv("CONFIRMATION_URL")
        validation_url = os.getenv("VALIDATION_URL")

        if not api_url or not confirmation_url or not validation_url:
            return JsonResponse({"error": "One or more required URLs are missing in .env"}, status=500)

        c2b_shortcode = os.getenv("C2B_SHORTCODE") or LipanaMpesaPassword.BUSINESS_SHORT_CODE

        payload = {
            "ShortCode": c2b_shortcode,
            "ResponseType": "Completed",
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"error": "Invalid JSON response", "status_code": response.status_code}

        # Safaricom sandbox can return a duplicate registration error if the shortcode
        # is already registered with the same notification info. Treat this as idempotent.
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
    """Handles validation callback"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

@csrf_exempt
def confirmation(request):
    """Handles confirmation callback and saves transaction details"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        mpesa_body = _json_body(request)

        # Log the incoming confirmation request
        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="Confirmation Callback",
            conversation_id=mpesa_body.get("TransID", ""),
            content=json.dumps(mpesa_body),
        )

        MpesaPayment.objects.create(
            transaction_id=mpesa_body.get("TransID"),
            amount=mpesa_body.get("TransAmount", 0),
            transaction_date=_parse_mpesa_timestamp(mpesa_body.get("TransTime")),
            phone_number=mpesa_body.get("MSISDN"),
            status="successful",
            result_code=0,
            result_description="C2B Confirmation",
        )

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def stk_push_callback(request):
    """Handles STK Push callback from M-Pesa (Success or Failure)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        raw = _json_body(request)
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

        transaction_date = _parse_mpesa_timestamp(transaction_date)

        # Determine transaction status
        status = "successful" if result_code == 0 else "failed"

        # Save the transaction
        MpesaPayment.objects.create(
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_description=result_desc,
            amount=amount,
            mpesa_receipt_number=mpesa_receipt_number,
            transaction_date=transaction_date,
            phone_number=phone_number,
            status=status
        )

        # Save the callback data for debugging/logging
        MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Callback",
            conversation_id=merchant_request_id,
            content=stk_callback_data,
            result_code=result_code,
            result_description=result_desc
        )

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Received Successfully"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def stk_push_error(request):
    """Handles STK Push errors (e.g., invalid request, insufficient funds)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        error_data = _json_body(request)

        merchant_request_id = error_data.get("MerchantRequestID", "")
        result_code = error_data.get("ResultCode", "")
        result_desc = error_data.get("ResultDesc", "")

        MpesaCallBacks.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Error",
            conversation_id=merchant_request_id,
            content=error_data,
            result_code=result_code,
            result_description=result_desc
        )

        return JsonResponse({"status": "error received"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@require_internal_api_key
def completed_transactions(request):
    """Fetch completed M-Pesa transactions with optional filters"""
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
            status_filter = status_filter.lower()
            if status_filter in ["failed", "successful"]:
                transactions = transactions.filter(status__iexact=status_filter)
            else:
                return JsonResponse({"error": "Invalid status. Use 'failed' or 'successful'."}, status=400)
        else:
            transactions = transactions.filter(status="successful")

        transactions_data = list(transactions.values())
        return JsonResponse({"transactions": transactions_data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@require_internal_api_key
def all_transactions(request):
    """Fetch all M-Pesa transactions"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        transactions = MpesaPayment.objects.all()
        transactions_data = list(transactions.values())
        return JsonResponse({"transactions": transactions_data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)