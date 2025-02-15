from django.shortcuts import render
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

load_dotenv()

def get_access_token(request):
    consumer_key = os.getenv('CONSUMER_KEY')
    consumer_secret = os.getenv('CONSUMER_SECRET')
    api_URL = os.getenv('TOKEN_URL')

    r = requests.get(api_URL, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    mpesa_access_token = json.loads(r.text)

    validated_mpesa_access_token = mpesa_access_token.get('access_token')

    if validated_mpesa_access_token:
        return JsonResponse({"access_token": validated_mpesa_access_token})
    else:
        return JsonResponse({"error": "Failed to retrieve access token"}, status=500)

@csrf_exempt
def lipa_na_mpesa_online(request):
    """Initiates Lipa Na Mpesa Online Payment (STK Push)"""
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("LIPA_NA_MPESA_ONLINE_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        password, timestamp = LipanaMpesaPassword.generate_password()

        payload = {
            "BusinessShortCode": LipanaMpesaPassword.BUSINESS_SHORT_CODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": 1,
            "PartyA": os.getenv("PARTY_A"),
            "PartyB": LipanaMpesaPassword.BUSINESS_SHORT_CODE,
            "PhoneNumber": os.getenv("PHONE_NUMBER"),
            "CallBackURL": os.getenv("CALL_BACK_URL"),
            "AccountReference": os.getenv("ACCOUNT_REFERENCE"),
            "TransactionDesc": "Testing STK push"
        }

        # Log the outgoing request
        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="STK Push Request",
            conversation_id=payload.get("AccountReference", ""),
            content=json.dumps(payload),
        )

        response = requests.post(api_url, json=payload, headers=headers)
        response_data = response.json()

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def register_urls(request):
    """Registers Mpesa Confirmation and Validation URLs"""
    try:
        access_token = MpesaC2bCredential.get_access_token()
        api_url = os.getenv("REGISTER_URL")
        headers = {"Authorization": f"Bearer {access_token}"}

        # Fetch URLs from env
        confirmation_url = os.getenv("CONFIRMATION_URL")
        validation_url = os.getenv("VALIDATION_URL")

        # Debugging prints
        print(f"REGISTER_URL: {api_url}")
        print(f"CONFIRMATION_URL: {confirmation_url}")
        print(f"VALIDATION_URL: {validation_url}")

        if not api_url or not confirmation_url or not validation_url:
            return JsonResponse({"error": "One or more required URLs are missing in .env"}, status=500)

        payload = {
            "ShortCode": LipanaMpesaPassword.BUSINESS_SHORT_CODE,
            "ResponseType": "Completed",
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url
        }

        response = requests.post(api_url, json=payload, headers=headers)
        response_data = response.json()

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def validation(request):
    """Handles validation callback"""
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

@csrf_exempt
def confirmation(request):
    """Handles confirmation callback and saves transaction details"""
    try:
        mpesa_body = json.loads(request.body.decode("utf-8"))

        # Log the incoming confirmation request
        MpesaCalls.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            caller="Confirmation Callback",
            conversation_id=mpesa_body.get("TransID", ""),
            content=json.dumps(mpesa_body),
        )

        payment = MpesaPayment(
            first_name=mpesa_body.get("FirstName", ""),
            last_name=mpesa_body.get("LastName", ""),
            middle_name=mpesa_body.get("MiddleName", ""),
            description=mpesa_body.get("TransID", ""),
            phone_number=mpesa_body.get("MSISDN", ""),
            amount=mpesa_body.get("TransAmount", 0),
            reference=mpesa_body.get("BillRefNumber", ""),
            organization_balance=mpesa_body.get("OrgAccountBalance", ""),
            type=mpesa_body.get("TransactionType", ""),
        )
        payment.save()

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def stk_push_callback(request):
    """Handles STK Push callback from M-Pesa (Success or Failure)"""
    try:
        stk_callback_data = json.loads(request.body.decode("utf-8"))

        merchant_request_id = stk_callback_data.get("MerchantRequestID", "")
        checkout_request_id = stk_callback_data.get("CheckoutRequestID", "")
        result_code = stk_callback_data.get("ResultCode", "")
        result_desc = stk_callback_data.get("ResultDesc", "")

        callback_metadata = stk_callback_data.get("CallbackMetadata", {}).get("Item", [])
        transaction_data = {item["Name"]: item["Value"] for item in callback_metadata}

        mpesa_receipt_number = transaction_data.get("MpesaReceiptNumber", "")
        amount = transaction_data.get("Amount", 0)
        transaction_date = transaction_data.get("TransactionDate", None)
        phone_number = transaction_data.get("PhoneNumber", "")

        # Convert transaction date to a valid format
        if transaction_date:
            transaction_date = datetime.datetime.strptime(str(transaction_date), "%Y%m%d%H%M%S")

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
    try:
        error_data = json.loads(request.body.decode("utf-8"))

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
    
def completed_transactions(request):
    """Fetch completed M-Pesa transactions with optional filters"""
    try:
        date_filter = request.GET.get("date", None)
        status_filter = request.GET.get("status", None)

        transactions = MpesaPayment.objects.filter(status="successful")

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

        transactions_data = list(transactions.values())
        return JsonResponse({"transactions": transactions_data}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def all_transactions(request):
    """Fetch all M-Pesa transactions"""
    try:
        transactions = MpesaPayment.objects.all()
        transactions_data = list(transactions.values())
        return JsonResponse({"transactions": transactions_data}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)