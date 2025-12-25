from django.contrib import admin

from .models import BulkBusinessPaymentBatch, BulkBusinessPaymentItem


@admin.register(BulkBusinessPaymentBatch)
class BulkBusinessPaymentBatchAdmin(admin.ModelAdmin):
	list_display = ("id", "status", "reference", "created_at")
	search_fields = ("id", "reference", "status")
	list_filter = ("status",)


@admin.register(BulkBusinessPaymentItem)
class BulkBusinessPaymentItemAdmin(admin.ModelAdmin):
	list_display = ("id", "batch", "recipient", "amount", "currency", "status", "created_at")
	search_fields = ("recipient", "item_reference", "status")
	list_filter = ("status", "currency")

# Register your models here.
