# Generated manually (environment lacks Django tooling).

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Business",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=120)),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[("active", "Active"), ("suspended", "Suspended")],
                        default="active",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BusinessMember",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("owner", "Owner"),
                            ("admin", "Admin"),
                            ("maker", "Maker"),
                            ("checker", "Checker"),
                            ("viewer", "Viewer"),
                        ],
                        default="viewer",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="business_api.business",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
                "unique_together": {("business", "user")},
            },
        ),
        migrations.CreateModel(
            name="DarajaCredential",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "environment",
                    models.CharField(
                        max_length=20,
                        choices=[("sandbox", "Sandbox"), ("production", "Production")],
                        default="sandbox",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("consumer_key", models.CharField(max_length=200)),
                ("consumer_secret", models.CharField(max_length=200)),
                ("token_url", models.URLField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daraja_credentials",
                        to="business_api.business",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MpesaShortcode",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "shortcode",
                    models.CharField(max_length=20, db_index=True),
                ),
                (
                    "shortcode_type",
                    models.CharField(
                        max_length=20,
                        choices=[("paybill", "PayBill"), ("till", "Till")],
                        default="paybill",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("lipa_passkey", models.CharField(max_length=200, blank=True, default="")),
                (
                    "default_account_reference_prefix",
                    models.CharField(max_length=40, blank=True, default=""),
                ),
                (
                    "default_stk_callback_url",
                    models.URLField(blank=True, default=""),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shortcodes",
                        to="business_api.business",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("business", "shortcode")},
            },
        ),
    ]
