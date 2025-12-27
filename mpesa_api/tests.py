import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business, MpesaShortcode, OAuthClientBusiness

from .models import MpesaCallBacks, MpesaCalls, MpesaPayment, StkPushInitiation
from .models import MpesaTransactionStatusQuery
from .views import (
    admin_calls_log,
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

    def test_confirmation_is_idempotent_for_same_transid(self):
        payload1 = {
            "TransID": "ABC999",
            "TransAmount": 10,
            "MSISDN": "254700000000",
            "TransTime": "20251223112233",
        }
        payload2 = {
            "TransID": "ABC999",
            "TransAmount": 12,
            "MSISDN": "254700000000",
            "TransTime": "20251223112233",
        }

        r1 = self.factory.post(
            "/api/v1/c2b/confirmation",
            data=json.dumps(payload1),
            content_type="application/json",
        )
        r2 = self.factory.post(
            "/api/v1/c2b/confirmation",
            data=json.dumps(payload2),
            content_type="application/json",
        )

        resp1 = confirmation(r1)
        resp2 = confirmation(r2)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        self.assertEqual(MpesaPayment.objects.count(), 1)
        payment = MpesaPayment.objects.first()
        self.assertEqual(payment.transaction_id, "ABC999")
        self.assertEqual(float(payment.amount), 12.0)

    def test_confirmation_sets_business_from_business_shortcode(self):
        biz = Business.objects.create(name="Biz")
        MpesaShortcode.objects.create(business=biz, shortcode="600111")
        payload = {
            "TransID": "ABC124",
            "TransAmount": 10,
            "MSISDN": "254700000000",
            "TransTime": "20251223112233",
            "BusinessShortCode": "600111",
        }
        request = self.factory.post(
            "/api/v1/c2b/confirmation",
            data=json.dumps(payload),
            content_type="application/json",
        )

        response = confirmation(request)
        self.assertEqual(response.status_code, 200)
        payment = MpesaPayment.objects.filter(transaction_id="ABC124").first()
        self.assertIsNotNone(payment)
        self.assertEqual(str(payment.business_id), str(biz.id))

        call_row = MpesaCalls.objects.first()
        self.assertIsNotNone(call_row)
        self.assertEqual(str(call_row.business_id), str(biz.id))

    def test_stk_callback_parses_nested_body_and_persists(self):
        biz = Business.objects.create(name="Biz")
        sc = MpesaShortcode.objects.create(business=biz, shortcode="174379", lipa_passkey="pass")
        StkPushInitiation.objects.create(
            business=biz,
            shortcode=sc,
            merchant_request_id="merch-1",
            checkout_request_id="chk-1",
        )

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
        self.assertEqual(str(payment.business_id), str(biz.id))
        self.assertEqual(payment.shortcode_id, sc.id)
        self.assertEqual(MpesaCallBacks.objects.count(), 1)

        cb = MpesaCallBacks.objects.first()
        self.assertIsNotNone(cb)
        self.assertEqual(str(cb.business_id), str(biz.id))
        self.assertEqual(cb.shortcode_id, sc.id)

    def test_stk_callback_is_idempotent_for_same_checkout_request_id(self):
        biz = Business.objects.create(name="Biz")
        sc = MpesaShortcode.objects.create(business=biz, shortcode="174379", lipa_passkey="pass")
        StkPushInitiation.objects.create(
            business=biz,
            shortcode=sc,
            merchant_request_id="merch-2",
            checkout_request_id="chk-2",
        )

        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merch-2",
                    "CheckoutRequestID": "chk-2",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 1},
                            {"Name": "MpesaReceiptNumber", "Value": "XYZ999"},
                            {"Name": "TransactionDate", "Value": "20251223120000"},
                            {"Name": "PhoneNumber", "Value": "254700000000"},
                        ]
                    },
                }
            }
        }

        req1 = self.factory.post(
            "/api/v1/stk/callback",
            data=json.dumps(payload),
            content_type="application/json",
        )
        req2 = self.factory.post(
            "/api/v1/stk/callback",
            data=json.dumps(payload),
            content_type="application/json",
        )

        resp1 = stk_push_callback(req1)
        resp2 = stk_push_callback(req2)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        self.assertEqual(MpesaPayment.objects.count(), 1)
        payment = MpesaPayment.objects.first()
        self.assertEqual(payment.checkout_request_id, "chk-2")
        self.assertEqual(payment.status, "successful")

        # Callback rows may be duplicated; payment should not.
        self.assertGreaterEqual(MpesaCallBacks.objects.count(), 1)

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
        self.business = Business.objects.create(name="Biz")
        OAuthClientBusiness.objects.create(application=self.application, business=self.business)

    def _create_access_token(self, scope: str) -> str:
        User = get_user_model()
        user = User.objects.create_user(username="oauth-owner", password="pw")
        app = Application.objects.create(
            name="test-app",
            user=user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        self.application = app
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

    def test_transaction_status_query_requires_scope(self):
        with patch.dict(
            os.environ,
            {
                "MPESA_TXN_STATUS_QUERY_URL": "https://example.invalid/query",
                "MPESA_TXN_STATUS_INITIATOR_NAME": "initiator",
                "MPESA_TXN_STATUS_SECURITY_CREDENTIAL": "cred",
                "MPESA_TXN_STATUS_RESULT_URL": "https://example.invalid/result",
                "MPESA_TXN_STATUS_TIMEOUT_URL": "https://example.invalid/timeout",
                "MPESA_TXN_STATUS_PARTY_A": "600000",
            },
            clear=False,
        ):
            # Token lacks transactions:write
            req = self.factory.post(
                "/api/v1/c2b/transaction-status/query",
                data=json.dumps({"transaction_id": "XYZ"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )
            from c2b_api.views import transaction_status_query

            resp = transaction_status_query(req)
            self.assertEqual(resp.status_code, 403)


class TransactionStatusQueryDefaultsFromShortcodeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pw")
        self.business = Business.objects.create(name="Biz")
        self.shortcode = MpesaShortcode.objects.create(
            business=self.business,
            shortcode="600999",
            shortcode_type="paybill",
            is_active=True,
            txn_status_initiator_name="init1",
            txn_status_security_credential="sec1",
            txn_status_result_url="https://example.com/result",
            txn_status_timeout_url="https://example.com/timeout",
            txn_status_identifier_type="4",
        )

        self.application = Application.objects.create(
            name="app",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            user=self.user,
        )
        OAuthClientBusiness.objects.create(application=self.application, business=self.business)

        self.token = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="t1",
            scope="transactions:write",
            expires=timezone.now() + timedelta(hours=1),
        )

    @patch("c2b_api.views.MpesaC2bCredential.get_access_token", return_value="token")
    @patch("c2b_api.views.requests.post")
    def test_uses_active_shortcode_defaults_when_missing(self, post_mock, _tok):
        post_mock.return_value.status_code = 200
        post_mock.return_value.json.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "Accepted",
            "OriginatorConversationID": "ocid",
            "ConversationID": "cid",
        }

        with patch.dict(
            os.environ,
            {
                "MPESA_TXN_STATUS_QUERY_URL": "https://example.invalid/txn-status",
                "MPESA_TXN_STATUS_PARTY_A": "600000",
            },
            clear=False,
        ):
            client = Client(HTTP_AUTHORIZATION=f"Bearer {self.token.token}")
            resp = client.post(
                "/api/v1/c2b/transaction-status/query",
                data=json.dumps({"transaction_id": "ABC123"}),
                content_type="application/json",
            )

        self.assertEqual(resp.status_code, 201, msg=getattr(resp, "content", b"").decode("utf-8", errors="ignore"))
        self.assertTrue(post_mock.called)
        sent_payload = post_mock.call_args.kwargs.get("json")
        self.assertIsNotNone(sent_payload)
        self.assertEqual(sent_payload.get("Initiator"), "init1")
        self.assertEqual(sent_payload.get("SecurityCredential"), "sec1")
        self.assertEqual(sent_payload.get("IdentifierType"), "4")
        self.assertEqual(sent_payload.get("ResultURL"), "https://example.com/result")
        self.assertEqual(sent_payload.get("QueueTimeOutURL"), "https://example.com/timeout")


class AdminLogsAuthTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

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


class TransactionStatusCallbackTests(TestCase):

    def test_transaction_status_result_updates_pending_payment(self):
        MpesaPayment.objects.create(transaction_id="XYZ123", status="pending", amount=1)
        MpesaTransactionStatusQuery.objects.create(
            transaction_id="XYZ123",
            originator_conversation_id="orig-1",
            status="pending",
        )

        payload = {
            "Result": {
                "OriginatorConversationID": "orig-1",
                "ConversationID": "conv-1",
                "ResultCode": 0,
                "ResultDesc": "OK",
                "ResultParameters": {
                    "ResultParameter": [
                        {"Key": "ReceiptNo", "Value": "XYZ123"},
                    ]
                },
            }
        }

        resp = self.client.post(
            "/api/v1/c2b/transaction-status/result",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        q = MpesaTransactionStatusQuery.objects.get(originator_conversation_id="orig-1")
        self.assertEqual(q.status, "successful")
        self.assertEqual(q.result_code, 0)

        p = MpesaPayment.objects.get(transaction_id="XYZ123")
        self.assertEqual(p.status, "successful")


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
        self.business = Business.objects.create(name="Biz")
        OAuthClientBusiness.objects.create(application=self.application, business=self.business)

    def _create_access_token(self, scope: str) -> str:
        User = get_user_model()
        user = User.objects.create_user(username="oauth-owner", password="pw")
        app = Application.objects.create(
            name="test-app",
            user=user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        self.application = app
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


class BootstrapSuperuserTests(TestCase):
    def setUp(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)
        os.environ["BOOTSTRAP_SUPERUSER_TOKEN"] = "test-bootstrap-token"

    def tearDown(self):
        os.environ.pop("BOOTSTRAP_SUPERUSER_TOKEN", None)

    def test_bootstrap_requires_token(self):
        resp = self.client.post(
            "/api/v1/bootstrap/superuser",
            data=json.dumps({"username": "admin", "password": "pw"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_bootstrap_creates_first_superuser(self):
        User = get_user_model()
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

        resp = self.client.post(
            "/api/v1/bootstrap/superuser",
            data=json.dumps({"username": "admin", "password": "pw", "email": "a@example.com"}),
            content_type="application/json",
            HTTP_X_BOOTSTRAP_TOKEN="test-bootstrap-token",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username="admin", is_superuser=True).exists())

    def test_bootstrap_is_blocked_once_superuser_exists(self):
        User = get_user_model()
        User.objects.create_superuser(username="existing", email="e@example.com", password="pw")

        resp = self.client.post(
            "/api/v1/bootstrap/superuser",
            data=json.dumps({"username": "admin2", "password": "pw"}),
            content_type="application/json",
            HTTP_X_BOOTSTRAP_TOKEN="test-bootstrap-token",
        )
        self.assertEqual(resp.status_code, 409)
