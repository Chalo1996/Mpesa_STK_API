import json
import os
from unittest.mock import patch

from django.test import TestCase

from .models import RatibaOrder


class RatibaApiTests(TestCase):
    def setUp(self):
        os.environ["INTERNAL_API_KEY"] = "test-key"
        os.environ["MPESA_RATIBA_URL"] = "https://example.invalid/mpesa/ratiba"

    def test_create_requires_api_key(self):
        resp = self.client.post(
            "/api/v1/ratiba/create",
            data=json.dumps({"foo": "bar"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    @patch("ratiba_api.views.MpesaC2bCredential.get_access_token", return_value="token")
    @patch("ratiba_api.views.requests.post")
    def test_create_persists_success(self, post, _tok):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"status": "ok"}

        resp = self.client.post(
            "/api/v1/ratiba/create",
            data=json.dumps(
                {
                    "StandingOrderName": "Test Standing Order",
                    "StartDate": "20240905",
                    "EndDate": "20250905",
                    "BusinessShortCode": "174379",
                    "TransactionType": "Standing Order Customer Pay Bill",
                    "ReceiverPartyIdentifierType": "4",
                    "Amount": "4500",
                    "PartyA": "254708374149",
                    "CallBackURL": "https://example.invalid/pat",
                    "AccountReference": "Test",
                    "TransactionDesc": "Test",
                    "Frequency": "2",
                }
            ),
            content_type="application/json",
            HTTP_X_API_KEY="test-key",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RatibaOrder.objects.count(), 1)

    @patch("ratiba_api.views.MpesaC2bCredential.get_access_token", return_value="token")
    def test_create_validates_required_fields(self, _tok):
        resp = self.client.post(
            "/api/v1/ratiba/create",
            data=json.dumps({"StandingOrderName": "X"}),
            content_type="application/json",
            HTTP_X_API_KEY="test-key",
        )
        self.assertEqual(resp.status_code, 400)

    def test_history_requires_api_key(self):
        resp = self.client.get("/api/v1/ratiba/history")
        self.assertEqual(resp.status_code, 401)

    def test_history_returns_results(self):
        RatibaOrder.objects.create(request_payload={"a": 1}, response_status=200, response_payload={"b": 2})
        resp = self.client.get("/api/v1/ratiba/history", HTTP_X_API_KEY="test-key")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())
