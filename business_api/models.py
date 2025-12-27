import uuid

from django.conf import settings
from django.db import models


class Business(models.Model):
    """A tenant (shop/merchant) in the platform."""

    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    business_type = models.CharField(max_length=60, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=[(STATUS_ACTIVE, "Active"), (STATUS_SUSPENDED, "Suspended")],
        default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class BusinessMember(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_MAKER = "maker"
    ROLE_CHECKER = "checker"
    ROLE_VIEWER = "viewer"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_memberships")
    role = models.CharField(
        max_length=20,
        choices=[
            (ROLE_OWNER, "Owner"),
            (ROLE_ADMIN, "Admin"),
            (ROLE_MAKER, "Maker"),
            (ROLE_CHECKER, "Checker"),
            (ROLE_VIEWER, "Viewer"),
        ],
        default=ROLE_VIEWER,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("business", "user")]
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.business_id} ({self.role})"


class DarajaCredential(models.Model):
    """Per-business Daraja consumer credentials.

    Note: these secrets should be treated as sensitive.
    """

    ENV_SANDBOX = "sandbox"
    ENV_PRODUCTION = "production"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="daraja_credentials")
    environment = models.CharField(
        max_length=20,
        choices=[(ENV_SANDBOX, "Sandbox"), (ENV_PRODUCTION, "Production")],
        default=ENV_SANDBOX,
    )
    is_active = models.BooleanField(default=True)

    consumer_key = models.CharField(max_length=200)
    consumer_secret = models.CharField(max_length=200)

    token_url = models.URLField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.business_id} ({self.environment})"


class MpesaShortcode(models.Model):
    """A PayBill/Till registered under a business."""

    TYPE_PAYBILL = "paybill"
    TYPE_TILL = "till"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="shortcodes")
    shortcode = models.CharField(max_length=20, db_index=True)
    shortcode_type = models.CharField(
        max_length=20,
        choices=[(TYPE_PAYBILL, "PayBill"), (TYPE_TILL, "Till")],
        default=TYPE_PAYBILL,
    )
    is_active = models.BooleanField(default=True)

    # STK-specific (Lipa Na Mpesa Online)
    lipa_passkey = models.CharField(max_length=200, blank=True, default="")

    # Optional defaults for onboarding convenience
    default_account_reference_prefix = models.CharField(max_length=40, blank=True, default="")
    default_stk_callback_url = models.URLField(blank=True, default="")
    default_ratiba_callback_url = models.URLField(blank=True, default="")

    # Transaction Status Query (reconciliation) defaults
    txn_status_initiator_name = models.CharField(max_length=120, blank=True, default="")
    txn_status_security_credential = models.CharField(max_length=500, blank=True, default="")
    txn_status_result_url = models.URLField(blank=True, default="")
    txn_status_timeout_url = models.URLField(blank=True, default="")
    txn_status_identifier_type = models.CharField(max_length=8, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("business", "shortcode")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.shortcode} ({self.shortcode_type})"


class OAuthClientBusiness(models.Model):
    """Bind an OAuth2 client_credentials Application to a Business.

    This lets gateway callers omit `business_id` on most requests since the
    system can derive it from the Bearer token's Application.
    """

    id = models.BigAutoField(primary_key=True)
    application = models.OneToOneField(
        "oauth2_provider.Application",
        on_delete=models.CASCADE,
        related_name="business_binding",
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="oauth_clients")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.application_id} -> {self.business_id}"
