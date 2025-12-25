import json
import os

from django.test import TestCase


class B2BBulkApiTests(TestCase):
	def setUp(self):
		os.environ["INTERNAL_API_KEY"] = "test-key"

	def test_bulk_create_requires_api_key(self):
		resp = self.client.post(
			"/api/v1/b2b/bulk",
			data=json.dumps({"items": [{"recipient": "ACCT-001", "amount": "1"}]}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 401)

	def test_bulk_create_and_detail(self):
		headers = {"HTTP_X_API_KEY": "test-key"}
		create = self.client.post(
			"/api/v1/b2b/bulk",
			data=json.dumps(
				{
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

		detail = self.client.get(f"/api/v1/b2b/bulk/{batch_id}", **headers)
		self.assertEqual(detail.status_code, 200)
		detail_json = detail.json()
		self.assertEqual(detail_json["id"], batch_id)
		self.assertEqual(len(detail_json["items"]), 2)

# Create your tests here.
