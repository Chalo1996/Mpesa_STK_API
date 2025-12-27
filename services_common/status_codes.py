from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps

from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Max



def _get_status_code_mapping_model():
    # Lazily resolve the model via the Django app registry.
    # This avoids import-time issues (and potential module shadowing) while still
    # keeping a single source of truth for system constants.
    return apps.get_model("status_codes", "StatusCodeMapping")


@dataclass(frozen=True)
class MappedStatus:
    status_code: int
    status_message: str
    external_system: str
    external_code: str


def _normalize_code(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_message(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def map_status(
    *,
    external_system: str,
    external_code,
    external_message=None,
    default_message: str | None = None,
) -> MappedStatus:
    """Get or create a mapping from (external_system, external_code) -> internal status.

    Internal codes are auto-assigned sequentially starting at 0.

    Message resolution order:
    1) mapping.default_message (if set)
    2) `default_message` (if provided)
    3) `external_message`
    4) empty string
    """

    code = _normalize_code(external_code)
    msg = _normalize_message(external_message)

    StatusCodeMapping = _get_status_code_mapping_model()

    if not code:
        # Treat missing/empty external codes as a gateway error category.
        external_system = StatusCodeMapping.SYSTEM_GATEWAY
        code = "UNKNOWN"

    # Fast path.
    existing = StatusCodeMapping.objects.filter(external_system=external_system, external_code=code).first()
    if existing:
        resolved_msg = (existing.default_message or "").strip() or (default_message or "").strip() or msg
        return MappedStatus(
            status_code=int(existing.internal_code),
            status_message=resolved_msg,
            external_system=external_system,
            external_code=code,
        )

    # Create path (race-safe).
    with transaction.atomic():
        # Ensure internal code 0 is reserved for Safaricom success.
        # This prevents the first-ever seen non-zero external code from taking internal code 0.
        if not StatusCodeMapping.objects.filter(internal_code=0).exists():
            try:
                StatusCodeMapping.objects.create(
                    external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
                    external_code="0",
                    internal_code=0,
                    default_message="Success",
                    is_success=True,
                )
            except IntegrityError:
                # Another concurrent request may have created it (or internal 0 is already taken).
                pass

        # Re-check under lock.
        existing = (
            StatusCodeMapping.objects.select_for_update()
            .filter(external_system=external_system, external_code=code)
            .first()
        )
        if existing:
            resolved_msg = (existing.default_message or "").strip() or (default_message or "").strip() or msg
            return MappedStatus(
                status_code=int(existing.internal_code),
                status_message=resolved_msg,
                external_system=external_system,
                external_code=code,
            )

        if external_system == StatusCodeMapping.SYSTEM_SAFARICOM and code == "0":
            next_internal = 0
        else:
            max_code = StatusCodeMapping.objects.select_for_update().aggregate(m=Max("internal_code")).get("m")
            next_internal = int(max_code or 0) + 1

        is_success = external_system == StatusCodeMapping.SYSTEM_SAFARICOM and code == "0"
        resolved_msg = (default_message or "").strip() or msg
        if is_success and not resolved_msg:
            resolved_msg = "Success"

        created = StatusCodeMapping.objects.create(
            external_system=external_system,
            external_code=code,
            internal_code=next_internal,
            default_message=resolved_msg if resolved_msg else "",
            is_success=is_success,
        )

        return MappedStatus(
            status_code=int(created.internal_code),
            status_message=(created.default_message or "").strip() or msg,
            external_system=external_system,
            external_code=code,
        )


def map_safaricom_status(*, code, message=None) -> MappedStatus:
    StatusCodeMapping = _get_status_code_mapping_model()
    return map_status(
        external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
        external_code=code,
        external_message=message,
    )


def apply_mapped_status(
    instance,
    *,
    external_system: str,
    external_code,
    external_message=None,
    code_field: str = "internal_status_code",
    message_field: str = "internal_status_message",
):
    mapped = map_status(
        external_system=external_system,
        external_code=external_code,
        external_message=external_message,
    )
    setattr(instance, code_field, mapped.status_code)
    setattr(instance, message_field, mapped.status_message)
    return mapped
