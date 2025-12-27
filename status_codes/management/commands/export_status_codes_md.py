from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from status_codes.models import StatusCodeMapping


class Command(BaseCommand):
    help = "Export StatusCodeMapping rows as a Markdown table"

    def handle(self, *args, **options):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

        rows = list(StatusCodeMapping.objects.all().order_by("internal_code"))  # type: ignore[attr-defined]

        self.stdout.write("# Status Codes")
        self.stdout.write("")
        self.stdout.write(
            "This file documents the internal gateway status codes exposed by this service. "
            "Internal codes start from 0 and map to external systems (e.g., Safaricom/Daraja)."
        )
        self.stdout.write("")
        self.stdout.write(f"Last generated: {now}")
        self.stdout.write("")
        self.stdout.write("Notes:")
        self.stdout.write("")
        self.stdout.write("- `status_code` / `status_message` are returned to integrators.")
        self.stdout.write(
            "- `status_message` typically comes from the stored `default_message` below (or the upstream message when no default is stored)."
        )
        self.stdout.write("")

        self.stdout.write("| internal_code | external_system | external_code | status_message | is_success |")
        self.stdout.write("| ---: | --- | --- | --- | :---: |")

        if not rows:
            self.stdout.write("| _(none yet)_ |  |  |  |  |")
            return

        def esc(value: str) -> str:
            return (value or "").replace("|", "\\|").replace("\n", " ").strip()

        for r in rows:
            status_message = (r.default_message or "").strip()
            if not status_message:
                status_message = "_(varies; from upstream)_"

            self.stdout.write(
                "| "
                + " | ".join(
                    [
                        str(r.internal_code),
                        esc(r.external_system),
                        esc(r.external_code),
                        esc(status_message),
                        "yes" if r.is_success else "no",
                    ]
                )
                + " |"
            )
