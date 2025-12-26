import json
import os
from datetime import timedelta

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from .models import MpesaCallBacks, MpesaCalls, MpesaPayment
from .views import (
	admin_calls_log,
	admin_callbacks_log,
	admin_stk_errors_log,
	all_transactions,
	confirmation,
	get_access_token,
	stk_push_callback,
)


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

	def test_stk_callback_endpoint_is_csrf_exempt(self):
		"""M-Pesa callbacks won't include CSRF cookies/tokens; endpoint must accept POST."""
		csrf_client = Client(enforce_csrf_checks=True)
		payload = {"Body": {"stkCallback": {"MerchantRequestID": "m", "CheckoutRequestID": "c"}}}
		response = csrf_client.post(
			"/api/v1/stk/callback",
			data=json.dumps(payload),
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)


class InternalAuthTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.access_token = self._create_access_token(scope="transactions:read")

	def _create_access_token(self, scope: str) -> str:
		User = get_user_model()
		user = User.objects.create_user(username="oauth-owner", password="pw")
		app = Application.objects.create(
			name="test-app",
			user=user,
			client_type=Application.CLIENT_CONFIDENTIAL,
			authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
		)
		token = "test-transactions-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token

	def test_get_access_token_requires_staff_session(self):
		request = self.factory.get("/api/v1/access/token")
		response = get_access_token(request)
		self.assertEqual(response.status_code, 401)

	def test_transactions_requires_bearer_token(self):
		request = self.factory.get("/api/v1/transactions/all")
		response = all_transactions(request)
		self.assertEqual(response.status_code, 401)

		request2 = self.factory.get(
			"/api/v1/transactions/all",
			HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
		)
		response2 = all_transactions(request2)
		self.assertEqual(response2.status_code, 200)

	def test_admin_calls_log_requires_api_key(self):
		request = self.factory.get("/api/v1/admin/logs/calls")
		response = admin_calls_log(request)
		self.assertEqual(response.status_code, 401)

	def test_admin_logs_return_data_when_authorized(self):
		MpesaCalls.objects.create(
			ip_address="127.0.0.1",
			caller="Test",
			conversation_id="c1",
			content="{}",
		)
		MpesaCallBacks.objects.create(
			ip_address="127.0.0.1",
			caller="STK Push Error",
			conversation_id="m1",
			content={"ResultCode": 1},
			result_code=1,
			result_description="Fail",
		)

		User = get_user_model()
		user = User.objects.create_user(username="staff", password="pw")
		user.is_staff = True
		user.save()
		self.client.force_login(user)

		resp_calls = self.client.get("/api/v1/admin/logs/calls")
		self.assertEqual(resp_calls.status_code, 200)
		self.assertIn("results", resp_calls.json())
		self.assertGreaterEqual(len(resp_calls.json()["results"]), 1)

		resp_callbacks = self.client.get("/api/v1/admin/logs/callbacks")
		self.assertEqual(resp_callbacks.status_code, 200)
		self.assertIn("results", resp_callbacks.json())
		self.assertGreaterEqual(len(resp_callbacks.json()["results"]), 1)

		resp_errors = self.client.get("/api/v1/admin/logs/stk-errors")
		self.assertEqual(resp_errors.status_code, 200)
		self.assertIn("results", resp_errors.json())
		self.assertGreaterEqual(len(resp_errors.json()["results"]), 1)


class SessionAuthCsrfTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.user = User.objects.create_user(username="staff", password="pw")
		self.user.is_staff = True
		self.user.save()

	def test_auth_login_requires_csrf(self):
		csrf_client = Client(enforce_csrf_checks=True)

		# No CSRF cookie/token -> blocked
		resp = csrf_client.post(
			"/api/v1/auth/login",
			data=json.dumps({"username": "staff", "password": "pw"}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 403)

		# Fetch CSRF cookie, then login with token
		csrf_client.get("/api/v1/auth/csrf")
		token = csrf_client.cookies.get("csrftoken").value
		resp2 = csrf_client.post(
			"/api/v1/auth/login",
			data=json.dumps({"username": "staff", "password": "pw"}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=token,
		)
		self.assertEqual(resp2.status_code, 200)

	def test_auth_logout_requires_csrf(self):
		csrf_client = Client(enforce_csrf_checks=True)
		csrf_client.get("/api/v1/auth/csrf")
		token = csrf_client.cookies.get("csrftoken").value

		# Login first
		resp_login = csrf_client.post(
			"/api/v1/auth/login",
			data=json.dumps({"username": "staff", "password": "pw"}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=token,
		)
		self.assertEqual(resp_login.status_code, 200)

		# Django can rotate CSRF token on login; use the current cookie value.
		token = csrf_client.cookies.get("csrftoken").value

		# Logout without token -> blocked
		resp_bad = csrf_client.post("/api/v1/auth/logout")
		self.assertEqual(resp_bad.status_code, 403)

		# Logout with token -> ok
		resp_ok = csrf_client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=token)
		self.assertEqual(resp_ok.status_code, 200)


class RateLimitMiddlewareTests(TestCase):
	def setUp(self):
		cache.clear()
		self.access_token = self._create_access_token(scope="transactions:read")

	def _create_access_token(self, scope: str) -> str:
		User = get_user_model()
		user = User.objects.create_user(username="oauth-owner", password="pw")
		app = Application.objects.create(
			name="test-app",
			user=user,
			client_type=Application.CLIENT_CONFIDENTIAL,
			authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
		)
		token = "test-rl-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token

	@override_settings(
		INTERNAL_RATE_LIMIT_ENABLED=True,
		INTERNAL_RATE_LIMIT_REQUESTS=2,
		INTERNAL_RATE_LIMIT_WINDOW_SECONDS=60,
		INTERNAL_RATE_LIMIT_PATHS=["/api/v1/transactions/all"],
	)
	def test_rate_limit_trips_on_protected_endpoint(self):
		# Use Django test client so middleware is applied.
		headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
		r1 = self.client.get("/api/v1/transactions/all", **headers)
		r2 = self.client.get("/api/v1/transactions/all", **headers)
		r3 = self.client.get("/api/v1/transactions/all", **headers)

		self.assertEqual(r1.status_code, 200)
		self.assertEqual(r2.status_code, 200)
		self.assertEqual(r3.status_code, 429)
