import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business, MpesaShortcode, OAuthClientBusiness

from .models import QrCode


class QrApiTests(TestCase):
    def setUp(self):
        os.environ["MPESA_QR_CODE_URL"] = "https://example.invalid/mpesa/qrcode"
        self.business = Business.objects.create(name="My Shop")
        self.shortcode = MpesaShortcode.objects.create(business=self.business, shortcode="174379", is_active=True)
        self.access_token, self.app = self._create_access_token(scope="qr:write")
        OAuthClientBusiness.objects.create(application=self.app, business=self.business)

    def _create_access_token(self, scope: str):
        User = get_user_model()
        user = User.objects.create_user(username="oauth-owner", password="pw")
        app = Application.objects.create(
            name="test-app",
            user=user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        token = "test-qr-token"
        AccessToken.objects.create(
            user=user,
            application=app,
            token=token,
            scope=scope,
            expires=timezone.now() + timedelta(hours=1),
        )
        return token, app

    def test_generate_requires_bearer_token(self):
        resp = self.client.post(
            "/api/v1/qr/generate",
            data=json.dumps({"MerchantName": "X", "RefNo": "1", "Amount": 1, "TrxCode": "BG"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    @patch("qr_api.views.MpesaC2bCredential.get_access_token", return_value="token")
    @patch("qr_api.views.requests.post")
    def test_generate_success(self, post, _tok):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"QRCode": "BASE64"}

        resp = self.client.post(
            "/api/v1/qr/generate",
            data=json.dumps(
                {
                    "RefNo": "INV-1",
                    "Amount": 123,
                    "TrxCode": "BG",
                    "Size": "300",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("QRCode"), "BASE64")

        self.assertEqual(QrCode.objects.count(), 1)
        record = QrCode.objects.first()
        self.assertEqual(record.ref_no, "INV-1")
        self.assertEqual(record.merchant_name, "My Shop")
        self.assertEqual(record.cpi, "174379")
        self.assertEqual(record.response_status, 200)
        self.assertEqual(record.qr_code_base64, "BASE64")

        # Ensure upstream call used bearer token.
        _args, kwargs = post.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")

    def test_history_requires_staff_session(self):
        resp = self.client.get("/api/v1/qr/history")
        self.assertEqual(resp.status_code, 401)

    def test_history_returns_results(self):
        QrCode.objects.create(
            merchant_name="My Shop",
            ref_no="INV-9",
            amount=1,
            trx_code="BG",
            request_payload={"RefNo": "INV-9"},
            response_status=200,
            response_payload={"QRCode": "X"},
            qr_code_base64="X",
        )

        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pw")
        staff.is_staff = True
        staff.save()
        self.client.force_login(staff)

        resp = self.client.get("/api/v1/qr/history")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(len(payload["results"]), 1)
