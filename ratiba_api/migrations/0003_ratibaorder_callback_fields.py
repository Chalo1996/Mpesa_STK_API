from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ratiba_api", "0002_alter_ratibaorder_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="ratibaorder",
            name="callback_payload",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="ratibaorder",
            name="callback_received_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ratibaorder",
            name="callback_result_code",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ratibaorder",
            name="callback_result_description",
            field=models.TextField(blank=True),
        ),
    ]
