from django.db import migrations


def seed_success_mapping(apps, _schema_editor):
    StatusCodeMapping = apps.get_model("status_codes", "StatusCodeMapping")

    # If internal code 0 is already taken by something else, do nothing.
    if StatusCodeMapping.objects.filter(internal_code=0).exists():
        return

    StatusCodeMapping.objects.create(
        external_system="safaricom",
        external_code="0",
        internal_code=0,
        default_message="Success",
        is_success=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("status_codes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_success_mapping, migrations.RunPython.noop),
    ]
