from django.test import TestCase

from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from business_api.models import Business, OAuthClientBusiness


class BusinessOnboardingTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="My Biz")

        self.app = Application.objects.create(
            user=None,
            name="client",
            client_id="cid",
            client_secret="secret",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            skip_authorization=True,
        )
        OAuthClientBusiness.objects.create(application=self.app, business=self.business)

        self.token = "tok"
        AccessToken.objects.create(
            token=self.token,
            application=self.app,
            expires=timezone.now() + timezone.timedelta(hours=1),
            scope="business:read business:write",
        )

    def test_onboarding_get_returns_business_context(self):
        resp = self.client.get(
            "/api/v1/business/onboarding",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload.get("business", {}).get("name"), "My Biz")

    def test_onboarding_post_upserts_shortcode_defaults(self):
        resp = self.client.post(
            "/api/v1/business/onboarding",
            data={
                "business_name": "My Biz Updated",
                "business_type": "retail",
                "shortcode": "174379",
                "shortcode_type": "paybill",
                "default_stk_callback_url": "https://example.invalid/stk/callback",
                "default_ratiba_callback_url": "https://example.invalid/ratiba/callback",
                "default_account_reference_prefix": "INV",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("business", {}).get("name"), "My Biz Updated")
        self.assertEqual(data.get("business", {}).get("business_type"), "retail")
        self.assertEqual(data.get("active_shortcode", {}).get("shortcode"), "174379")
        self.assertEqual(
            data.get("active_shortcode", {}).get("default_stk_callback_url"),
            "https://example.invalid/stk/callback",
        )

    def test_onboarding_post_requires_business_type_when_missing(self):
        resp = self.client.post(
            "/api/v1/business/onboarding",
            data={
                "business_name": "My Biz Updated",
                "shortcode": "174379",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("business_type", resp.json().get("error", ""))

    def test_onboarding_post_requires_business_write_scope(self):
        # overwrite token with read-only
        AccessToken.objects.filter(token=self.token).update(scope="business:read")

        resp = self.client.post(
            "/api/v1/business/onboarding",
            data={"shortcode": "174379"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 403)
