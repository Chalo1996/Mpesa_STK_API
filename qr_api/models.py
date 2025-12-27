import uuid

from django.conf import settings
from django.db import models

from mpesa_api.models import BaseModel


class QrCode(BaseModel):
    """Persisted record of Daraja QR generation requests and responses."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qr_codes",
    )

    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="qr_codes",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="qr_codes",
    )

    merchant_name = models.CharField(max_length=200)
    ref_no = models.CharField(max_length=120, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    trx_code = models.CharField(max_length=10)
    cpi = models.CharField(max_length=120, blank=True)
    size = models.CharField(max_length=20, blank=True)

    request_payload = models.JSONField(default=dict)
    response_status = models.IntegerField(blank=True, null=True)
    response_payload = models.JSONField(default=dict)
    qr_code_base64 = models.TextField(blank=True)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "QR Code"
        verbose_name_plural = "QR Codes"

    def __str__(self):
        return f"QR {self.ref_no} ({self.created_at:%Y-%m-%d %H:%M:%S})"
