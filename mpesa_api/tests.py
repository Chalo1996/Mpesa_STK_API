import json
import os

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from .models import MpesaCallBacks, MpesaCalls, MpesaPayment
from .views import all_transactions, confirmation, get_access_token, stk_push_callback


class MpesaViewsTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def test_confirmation_creates_payment_with_supported_fields(self):
		payload = {
			"TransID": "ABC123",
			"TransAmount": 10,
			"MSISDN": "254700000000",
			"TransTime": "20251223112233",
		}
		request = self.factory.post(
			"/api/v1/c2b/confirmation",
			data=json.dumps(payload),
			content_type="application/json",
		)

		response = confirmation(request)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(MpesaPayment.objects.count(), 1)
		payment = MpesaPayment.objects.first()
		self.assertEqual(payment.transaction_id, "ABC123")
		self.assertEqual(str(payment.phone_number), "254700000000")

		# Also logs the call
		self.assertEqual(MpesaCalls.objects.count(), 1)

	def test_stk_callback_parses_nested_body_and_persists(self):
		payload = {
			"Body": {
				"stkCallback": {
					"MerchantRequestID": "merch-1",
					"CheckoutRequestID": "chk-1",
					"ResultCode": 0,
					"ResultDesc": "Success",
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": 1},
							{"Name": "MpesaReceiptNumber", "Value": "XYZ"},
							{"Name": "TransactionDate", "Value": "20251223120000"},
							{"Name": "PhoneNumber", "Value": "254700000000"},
						]
					},
				}
			}
		}
		request = self.factory.post(
			"/api/v1/stk/callback",
			data=json.dumps(payload),
			content_type="application/json",
		)

		response = stk_push_callback(request)
		self.assertEqual(response.status_code, 200)

		self.assertEqual(MpesaPayment.objects.count(), 1)
		payment = MpesaPayment.objects.first()
		self.assertEqual(payment.merchant_request_id, "merch-1")
		self.assertEqual(payment.checkout_request_id, "chk-1")
		self.assertEqual(payment.status, "successful")
		self.assertEqual(MpesaCallBacks.objects.count(), 1)


class InternalAuthTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		os.environ["INTERNAL_API_KEY"] = "test-key"

	def test_get_access_token_requires_api_key(self):
		request = self.factory.get("/api/v1/access/token")
		response = get_access_token(request)
		self.assertEqual(response.status_code, 401)

	def test_transactions_requires_api_key(self):
		request = self.factory.get("/api/v1/transactions/all")
		response = all_transactions(request)
		self.assertEqual(response.status_code, 401)


class RateLimitMiddlewareTests(TestCase):
	def setUp(self):
		cache.clear()
		os.environ["INTERNAL_API_KEY"] = "test-key"

	@override_settings(
		INTERNAL_RATE_LIMIT_ENABLED=True,
		INTERNAL_RATE_LIMIT_REQUESTS=2,
		INTERNAL_RATE_LIMIT_WINDOW_SECONDS=60,
		INTERNAL_RATE_LIMIT_PATHS=["/api/v1/transactions/all"],
	)
	def test_rate_limit_trips_on_protected_endpoint(self):
		# Use Django test client so middleware is applied.
		headers = {"HTTP_X_API_KEY": "test-key"}
		r1 = self.client.get("/api/v1/transactions/all", **headers)
		r2 = self.client.get("/api/v1/transactions/all", **headers)
		r3 = self.client.get("/api/v1/transactions/all", **headers)

		self.assertEqual(r1.status_code, 200)
		self.assertEqual(r2.status_code, 200)
		self.assertEqual(r3.status_code, 429)
