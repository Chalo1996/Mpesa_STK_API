from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DEPRECATED: This project does not import Safaricom codes from .odt files."

    def handle(self, *args, **options):
        raise CommandError(
            "ODT import is not supported in this project. "
            "Populate StatusCodeMapping via Django admin or a version-controlled seed, then run: "
            "python manage.py export_status_codes_md > StatusCodes.md"
        )
