import uuid

from django.conf import settings
from django.db import models

from mpesa_api.models import BaseModel


class RatibaOrder(BaseModel):
    """Persisted record of M-Pesa Ratiba create requests and responses."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ratiba_orders",
    )

    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ratiba_orders",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ratiba_orders",
    )

    request_payload = models.JSONField(default=dict)
    response_status = models.IntegerField(blank=True, null=True)
    response_payload = models.JSONField(default=dict)
    error = models.TextField(blank=True)

    # Ratiba callback (asynchronous) details
    callback_received_at = models.DateTimeField(blank=True, null=True)
    callback_result_code = models.IntegerField(blank=True, null=True)
    callback_result_description = models.TextField(blank=True)
    callback_payload = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Ratiba Order"
        verbose_name_plural = "Ratiba Orders"

    def __str__(self):
        return f"RatibaOrder {self.id}"
