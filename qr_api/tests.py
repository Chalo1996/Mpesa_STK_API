import json
import os
from unittest.mock import patch

from django.test import TestCase

from .models import QrCode


class QrApiTests(TestCase):
    def setUp(self):
        os.environ["INTERNAL_API_KEY"] = "test-key"
        os.environ["MPESA_QR_CODE_URL"] = "https://example.invalid/mpesa/qrcode"

    def test_generate_requires_api_key(self):
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
                    "MerchantName": "My Shop",
                    "RefNo": "INV-1",
                    "Amount": 123,
                    "TrxCode": "BG",
                    "Size": "300",
                }
            ),
            content_type="application/json",
            HTTP_X_API_KEY="test-key",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("QRCode"), "BASE64")

        self.assertEqual(QrCode.objects.count(), 1)
        record = QrCode.objects.first()
        self.assertEqual(record.ref_no, "INV-1")
        self.assertEqual(record.response_status, 200)
        self.assertEqual(record.qr_code_base64, "BASE64")

        # Ensure upstream call used bearer token.
        _args, kwargs = post.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")

    def test_history_requires_api_key(self):
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
        resp = self.client.get("/api/v1/qr/history", HTTP_X_API_KEY="test-key")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(len(payload["results"]), 1)
