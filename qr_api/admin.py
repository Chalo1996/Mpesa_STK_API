from django.contrib import admin

from .models import QrCode


@admin.register(QrCode)
class QrCodeAdmin(admin.ModelAdmin):
	list_display = (
		"created_at",
		"ref_no",
		"merchant_name",
		"amount",
		"trx_code",
		"response_status",
	)
	search_fields = ("ref_no", "merchant_name")
	list_filter = ("trx_code", "response_status")
