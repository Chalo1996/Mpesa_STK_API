import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business
from business_api.models import DarajaCredential


class B2BBulkApiTests(TestCase):
	def setUp(self):
		self.access_token = self._create_access_token(scope="b2b:write")
		self.business = Business.objects.create(name="Shop B")
		DarajaCredential.objects.create(
			business=self.business,
			environment=DarajaCredential.ENV_SANDBOX,
			is_active=True,
			consumer_key="ck",
			consumer_secret="cs",
			token_url="https://example.com/token",
		)

	def _create_access_token(self, scope: str) -> str:
		User = get_user_model()
		user = User.objects.create_user(username="oauth-owner", password="pw")
		app = Application.objects.create(
			name="test-app",
			user=user,
			client_type=Application.CLIENT_CONFIDENTIAL,
			authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
		)
		token = "test-b2b-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token

	def test_bulk_create_requires_bearer_token(self):
		resp = self.client.post(
			"/api/v1/b2b/bulk",
			data=json.dumps({"items": [{"recipient": "ACCT-001", "amount": "1"}]}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 401)

	def test_bulk_create_and_detail(self):
		headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
		create = self.client.post(
			"/api/v1/b2b/bulk",
			data=json.dumps(
				{
					"business_id": str(self.business.id),
					"reference": "B2B-001",
					"items": [
						{"recipient": "ACCT-001", "amount": "1", "currency": "KES"},
						{"recipient": "ACCT-002", "amount": "2.50"},
					],
				}
			),
			content_type="application/json",
			**headers,
		)
		self.assertEqual(create.status_code, 201)
		payload = create.json()
		self.assertTrue(payload.get("ok"))
		batch_id = payload["batch"]["id"]
		self.assertEqual(payload["batch"]["business_id"], str(self.business.id))

		User = get_user_model()
		staff = User.objects.create_user(username="staff", password="pw")
		staff.is_staff = True
		staff.save()
		self.client.force_login(staff)

		detail = self.client.get(f"/api/v1/b2b/bulk/{batch_id}")
		self.assertEqual(detail.status_code, 200)
		detail_json = detail.json()
		self.assertEqual(detail_json["id"], batch_id)
		self.assertEqual(len(detail_json["items"]), 2)


class B2BSingleUssdApiTests(TestCase):
	def setUp(self):
		self.access_token = self._create_access_token(scope="b2b:write")
		self.business = Business.objects.create(name="Shop B")
		DarajaCredential.objects.create(
			business=self.business,
			environment=DarajaCredential.ENV_SANDBOX,
			is_active=True,
			consumer_key="ck",
			consumer_secret="cs",
			token_url="https://example.com/token",
		)

	def _create_access_token(self, scope: str) -> str:
		User = get_user_model()
		user = User.objects.create_user(username="oauth-owner", password="pw")
		app = Application.objects.create(
			name="test-app",
			user=user,
			client_type=Application.CLIENT_CONFIDENTIAL,
			authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
		)
		token = "test-b2b-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token

	def test_single_requires_bearer_token(self):
		resp = self.client.post(
			"/api/v1/b2b/single",
			data=json.dumps(
				{
					"business_id": str(self.business.id),
					"primary_short_code": "000001",
					"receiver_short_code": "000002",
					"amount": "100",
					"payment_ref": "paymentRef",
					"callback_url": "https://example.com/result",
					"partner_name": "Vendor",
				}
			),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 401)

	@patch.dict(
		os.environ,
		{
			"MPESA_B2B_USSD_API_URL": "https://sandbox.safaricom.co.ke/v1/ussdpush/get-msisdn",
			"MPESA_B2B_CALLBACK_URL": "https://example.com/result",
		},
	)
	@patch("b2b_api.views.requests.post")
	@patch("b2b_api.views.requests.get")
	def test_single_submits_and_persists(self, mock_get, mock_post):
		class FakeResp:
			def __init__(self, status_code, payload):
				self.status_code = status_code
				self._payload = payload
				self.text = json.dumps(payload)

			def json(self):
				return self._payload

		mock_get.return_value = FakeResp(200, {"access_token": "abc", "expires_in": "3599"})
		mock_post.return_value = FakeResp(200, {"code": "0", "status": "USSD Initiated Successfully"})

		headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
		resp = self.client.post(
			"/api/v1/b2b/single",
			data=json.dumps(
				{
					"business_id": str(self.business.id),
					"primary_short_code": "000001",
					"receiver_short_code": "000002",
					"amount": "100",
					"payment_ref": "paymentRef",
					"callback_url": "https://example.com/result",
					"partner_name": "Vendor",
					"request_ref_id": "req-1",
				}
			),
			content_type="application/json",
			**headers,
		)
		self.assertEqual(resp.status_code, 201)
		payload = resp.json()
		self.assertTrue(payload.get("ok"))
		ussd = payload.get("ussd_request")
		self.assertEqual(ussd.get("request_ref_id"), "req-1")
		self.assertEqual(ussd.get("response_code"), "0")

	def test_callback_result_updates_request(self):
		from b2b_api.models import B2BUSSDPushRequest

		req = B2BUSSDPushRequest.objects.create(
			business=self.business,
			environment="sandbox",
			request_ref_id="req-cb-1",
			request_payload={},
		)
		resp = self.client.post(
			"/api/v1/b2b/callback/result",
			data=json.dumps(
				{
					"resultCode": "0",
					"resultDesc": "The service request is processed successfully.",
					"amount": "71.0",
					"requestId": "req-cb-1",
					"conversationID": "AG_20230426_2010434680d9f5a73766",
					"transactionId": "RDQ01NFT1Q",
					"status": "SUCCESS",
				}
			),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 200)
		req.refresh_from_db()
		self.assertEqual(req.status, "success")
		self.assertEqual(req.result_code, "0")
		self.assertEqual(req.transaction_id, "RDQ01NFT1Q")

# Create your tests here.
