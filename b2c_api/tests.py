import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business
from business_api.models import DarajaCredential, OAuthClientBusiness


class B2CBulkApiTests(TestCase):
	def setUp(self):
		self.business = Business.objects.create(name="Shop A")
		self.access_token, self.app = self._create_access_token(scope="b2c:write")
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
		token = "test-b2c-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token, app

	def test_bulk_create_requires_bearer_token(self):
		resp = self.client.post(
			"/api/v1/b2c/bulk",
			data=json.dumps({"items": [{"recipient": "254700000000", "amount": "1"}]}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 401)

	def test_bulk_create_and_detail(self):
		headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
		create = self.client.post(
			"/api/v1/b2c/bulk",
			data=json.dumps(
				{
					"reference": "BATCH-001",
					"items": [
						{"recipient": "254700000000", "amount": "1", "currency": "KES"},
						{"recipient": "254711111111", "amount": "2.50"},
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

		detail = self.client.get(f"/api/v1/b2c/bulk/{batch_id}")
		self.assertEqual(detail.status_code, 200)
		detail_json = detail.json()
		self.assertEqual(detail_json["id"], batch_id)
		self.assertEqual(len(detail_json["items"]), 2)


class B2CSingleApiTests(TestCase):
	def setUp(self):
		self.business = Business.objects.create(name="Shop A")
		self.access_token, self.app = self._create_access_token(scope="b2c:write")
		OAuthClientBusiness.objects.create(application=self.app, business=self.business)
		DarajaCredential.objects.create(
			business=self.business,
			environment=DarajaCredential.ENV_SANDBOX,
			is_active=True,
			consumer_key="ck",
			consumer_secret="cs",
			token_url="https://example.com/token",
		)

	def _create_access_token(self, scope: str):
		User = get_user_model()
		user = User.objects.create_user(username="oauth-owner", password="pw")
		app = Application.objects.create(
			name="test-app",
			user=user,
			client_type=Application.CLIENT_CONFIDENTIAL,
			authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
		)
		token = "test-b2c-token"
		AccessToken.objects.create(
			user=user,
			application=app,
			token=token,
			scope=scope,
			expires=timezone.now() + timedelta(hours=1),
		)
		return token, app

	def test_single_requires_bearer_token(self):
		resp = self.client.post(
			"/api/v1/b2c/single",
			data=json.dumps({"party_b": "254700000000", "amount": "1"}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 401)

	@patch.dict(
		os.environ,
		{
			"MPESA_B2C_INITIATOR_NAME": "test-initiator",
			"MPESA_B2C_SECURITY_CREDENTIAL": "test-credential",
			"MPESA_B2C_QUEUE_TIMEOUT_URL": "https://example.com/timeout",
			"MPESA_B2C_RESULT_URL": "https://example.com/result",
			"MPESA_B2C_PARTY_A": "600000",
			"MPESA_B2C_API_BASE_URL": "https://sandbox.safaricom.co.ke",
		},
	)
	@patch("b2c_api.views.requests.post")
	@patch("b2c_api.views.requests.get")
	def test_single_submits_and_persists(self, mock_get, mock_post):
		class FakeResp:
			def __init__(self, status_code, payload):
				self.status_code = status_code
				self._payload = payload
				self.text = json.dumps(payload)

			def json(self):
				return self._payload

		mock_get.return_value = FakeResp(200, {"access_token": "abc", "expires_in": "3599"})
		mock_post.return_value = FakeResp(
			200,
			{
				"OriginatorConversationID": "orig-1",
				"ConversationID": "conv-1",
				"ResponseCode": "0",
				"ResponseDescription": "Accept the service request successfully.",
			},
		)

		headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
		resp = self.client.post(
			"/api/v1/b2c/single",
			data=json.dumps(
				{
					"party_b": "254700000000",
					"amount": "1",
					"originator_conversation_id": "orig-1",
					"remarks": "ok",
					"occasion": "", 
				}
			),
			content_type="application/json",
			**headers,
		)
		self.assertEqual(resp.status_code, 201)
		payload = resp.json()
		self.assertTrue(payload.get("ok"))
		self.assertEqual(payload["payment_request"]["originator_conversation_id"], "orig-1")
		self.assertEqual(payload["payment_request"]["conversation_id"], "conv-1")
		self.assertEqual(payload["payment_request"]["response_code"], "0")

	@patch.dict(os.environ, {}, clear=True)
	def test_callback_result_updates_request(self):
		from b2c_api.models import B2CPaymentRequest

		pr = B2CPaymentRequest.objects.create(
			business=self.business,
			environment="sandbox",
			originator_conversation_id="orig-cb-1",
			request_payload={},
		)
		resp = self.client.post(
			"/api/v1/b2c/callback/result",
			data=json.dumps(
				{
					"Result": {
						"OriginatorConversationID": "orig-cb-1",
						"ConversationID": "conv-cb-1",
						"ResultCode": 0,
						"ResultDesc": "The service request is processed successfully.",
						"TransactionID": "T123",
					}
				}
			),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 200)
		pr.refresh_from_db()
		self.assertEqual(pr.status, "result")
		self.assertEqual(pr.conversation_id, "conv-cb-1")
		self.assertEqual(pr.result_code, 0)
		self.assertEqual(pr.transaction_id, "T123")

	def test_single_list_requires_staff(self):
		from b2c_api.models import B2CPaymentRequest

		pr = B2CPaymentRequest.objects.create(
			business=self.business,
			environment="sandbox",
			originator_conversation_id="orig-list-1",
			request_payload={},
		)
		resp = self.client.get("/api/v1/b2c/single/list")
		self.assertEqual(resp.status_code, 401)

		User = get_user_model()
		staff = User.objects.create_user(username="staff", password="pw")
		staff.is_staff = True
		staff.save()
		self.client.force_login(staff)

		resp2 = self.client.get("/api/v1/b2c/single/list?limit=10")
		self.assertEqual(resp2.status_code, 200)
		data = resp2.json()
		self.assertTrue(isinstance(data.get("results"), list))
		self.assertTrue(any(r.get("id") == str(pr.id) for r in data.get("results")))

		resp3 = self.client.get(f"/api/v1/b2c/single/{pr.id}")
		self.assertEqual(resp3.status_code, 200)
		detail = resp3.json()
		self.assertEqual(detail["id"], str(pr.id))

# Create your tests here.
