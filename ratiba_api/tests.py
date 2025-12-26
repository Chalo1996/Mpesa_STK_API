import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from .models import RatibaOrder


class RatibaApiTests(TestCase):
    def setUp(self):
        os.environ["MPESA_RATIBA_URL"] = "https://example.invalid/mpesa/ratiba"
        self.access_token = self._create_access_token(scope="ratiba:write")

    def _create_access_token(self, scope: str) -> str:
        User = get_user_model()
        user = User.objects.create_user(username="oauth-owner", password="pw")
        app = Application.objects.create(
            name="test-app",
            user=user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        token = "test-ratiba-token"
        AccessToken.objects.create(
            user=user,
            application=app,
            token=token,
            scope=scope,
            expires=timezone.now() + timedelta(hours=1),
        )
        return token

    def test_create_requires_bearer_token(self):
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
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RatibaOrder.objects.count(), 1)

    @patch("ratiba_api.views.MpesaC2bCredential.get_access_token", return_value="token")
    def test_create_validates_required_fields(self, _tok):
        resp = self.client.post(
            "/api/v1/ratiba/create",
            data=json.dumps({"StandingOrderName": "X"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(resp.status_code, 400)

    def test_history_requires_staff_session(self):
        resp = self.client.get("/api/v1/ratiba/history")
        self.assertEqual(resp.status_code, 401)

    def test_history_returns_results(self):
        RatibaOrder.objects.create(request_payload={"a": 1}, response_status=200, response_payload={"b": 2})

        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pw")
        staff.is_staff = True
        staff.save()
        self.client.force_login(staff)

        resp = self.client.get("/api/v1/ratiba/history")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())
