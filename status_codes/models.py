from django.db import models


class StatusCodeMapping(models.Model):
    """Maps external status/error codes to internal gateway status codes.

    - `internal_code` starts at 0 and increments.
    - `external_system` allows mapping Safaricom codes and gateway/internal pseudo-codes.

    Notes:
    - This is intentionally generic so all apps can reuse it.
    """

    SYSTEM_SAFARICOM = "safaricom"
    SYSTEM_GATEWAY = "gateway"

    SYSTEM_CHOICES = [
        (SYSTEM_SAFARICOM, "Safaricom"),
        (SYSTEM_GATEWAY, "Gateway"),
    ]

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    external_system = models.CharField(max_length=20, choices=SYSTEM_CHOICES)
    external_code = models.CharField(max_length=80)

    internal_code = models.PositiveIntegerField(unique=True)

    default_message = models.TextField(blank=True, default="")
    is_success = models.BooleanField(default=False)

    class Meta:
        ordering = ["internal_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["external_system", "external_code"],
                name="uniq_status_code_mapping_external",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.external_system}:{self.external_code} -> {self.internal_code}"
