import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business


class B2BBulkApiTests(TestCase):
	def setUp(self):
		self.access_token = self._create_access_token(scope="b2b:write")
		self.business = Business.objects.create(name="Shop B")

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

# Create your tests here.
