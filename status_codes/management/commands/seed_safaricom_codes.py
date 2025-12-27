import json
import os
import re
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from status_codes.models import StatusCodeMapping


@dataclass(frozen=True)
class _SeedRow:
    external_code: str
    default_message: str
    is_success: bool


def _parse_code_sort_key(code: str):
    """Sort key for codes like '1032' or '400.003.01'.

    - Numeric codes sort numerically
    - Dot-delimited numeric codes sort by tuple
    - Otherwise sort lexicographically at the end
    """

    raw = (code or "").strip()
    if not raw:
        return (2, "")

    if raw.isdigit():
        return (0, (int(raw),))

    if re.fullmatch(r"\d+(?:\.\d+)+", raw):
        parts = tuple(int(p) for p in raw.split("."))
        return (0, parts)

    return (1, raw)


def _default_data_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_dir, "data", "safaricom_codes.json")


class Command(BaseCommand):
    help = "Seed StatusCodeMapping with a version-controlled Safaricom/Daraja code list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=_default_data_path(),
            help="Path to JSON file (default: status_codes/data/safaricom_codes.json)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing safaricom mappings before seeding (recommended for deterministic internal codes)",
        )

    def handle(self, *args, **options):
        file_path: str = options["file"]
        reset: bool = bool(options.get("reset"))

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Seed file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as fp:
            payload = json.load(fp)

        if not isinstance(payload, list):
            raise ValueError("Seed JSON must be a list of objects")

        rows: list[_SeedRow] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            external_code = str(item.get("external_code") or "").strip()
            default_message = str(item.get("default_message") or "")
            is_success = bool(item.get("is_success"))
            if not external_code:
                continue
            rows.append(_SeedRow(external_code=external_code, default_message=default_message, is_success=is_success))

        if reset:
            StatusCodeMapping.objects.filter(external_system=StatusCodeMapping.SYSTEM_SAFARICOM).delete()

        # Always ensure success mapping exists as internal 0.
        with transaction.atomic():
            StatusCodeMapping.objects.update_or_create(
                external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
                external_code="0",
                defaults={
                    "internal_code": 0,
                    "default_message": "Success",
                    "is_success": True,
                },
            )

        # Deduplicate by external_code (prefer non-empty message).
        by_code: dict[str, _SeedRow] = {}
        for r in rows:
            if r.external_code == "0":
                continue
            existing = by_code.get(r.external_code)
            if not existing:
                by_code[r.external_code] = r
                continue
            if (not (existing.default_message or "").strip()) and (r.default_message or "").strip():
                by_code[r.external_code] = r

        created = 0
        updated = 0

        # If reset was used, make internal codes deterministic by assigning in sorted order.
        # Otherwise, preserve existing internal codes and only fill missing mappings.
        if reset:
            next_internal = 1
            for code, r in sorted(by_code.items(), key=lambda kv: _parse_code_sort_key(kv[0])):
                with transaction.atomic():
                    obj, was_created = StatusCodeMapping.objects.update_or_create(
                        external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
                        external_code=code,
                        defaults={
                            "internal_code": next_internal,
                            "default_message": r.default_message or "",
                            "is_success": bool(r.is_success),
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                    next_internal += 1
        else:
            for code, r in sorted(by_code.items(), key=lambda kv: _parse_code_sort_key(kv[0])):
                obj = StatusCodeMapping.objects.filter(
                    external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
                    external_code=code,
                ).first()
                if obj:
                    new_msg = (r.default_message or "").strip()
                    if new_msg and not (obj.default_message or "").strip():
                        obj.default_message = new_msg
                        obj.is_success = bool(r.is_success)
                        obj.save(update_fields=["default_message", "is_success", "updated_at"])
                        updated += 1
                    continue

                # Allocate next internal code (append after current max).
                max_code = StatusCodeMapping.objects.order_by("-internal_code").values_list("internal_code", flat=True).first()
                next_internal = int(max_code or 0) + 1
                StatusCodeMapping.objects.create(
                    external_system=StatusCodeMapping.SYSTEM_SAFARICOM,
                    external_code=code,
                    internal_code=next_internal,
                    default_message=r.default_message or "",
                    is_success=bool(r.is_success),
                )
                created += 1

        self.stdout.write(f"Seeded safaricom mappings. created={created}, updated={updated}")
