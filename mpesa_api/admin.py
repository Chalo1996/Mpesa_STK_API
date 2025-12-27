from django.contrib import admin

from .models import MpesaCallBacks, MpesaCalls, MpesaPayment, StkPushCallback, StkPushError

@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "amount",
        "phone_number",
        "mpesa_receipt_number",
        "transaction_id",
        "merchant_request_id",
        "checkout_request_id",
        "business",
        "shortcode",
    )
    list_filter = ("status", "created_at", "business")
    search_fields = (
        "transaction_id",
        "mpesa_receipt_number",
        "phone_number",
        "merchant_request_id",
        "checkout_request_id",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(MpesaCalls)
class MpesaCallsAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "caller",
        "ip_address",
        "conversation_id",
        "business",
        "shortcode",
    )
    list_filter = ("caller", "created_at", "business")
    search_fields = ("caller", "conversation_id", "ip_address", "content")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(MpesaCallBacks)
class MpesaCallBacksAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "caller",
        "ip_address",
        "conversation_id",
        "result_code",
        "business",
        "shortcode",
    )
    list_filter = ("caller", "result_code", "created_at", "business")
    search_fields = ("caller", "conversation_id", "ip_address")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "content")


@admin.register(StkPushCallback)
class StkPushCallbackAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "merchant_request_id",
        "checkout_request_id",
        "response_code",
    )
    list_filter = ("status", "response_code", "created_at")
    search_fields = ("merchant_request_id", "checkout_request_id", "response_code")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(StkPushError)
class StkPushErrorAdmin(admin.ModelAdmin):
    list_display = ("created_at", "merchant_request_id", "error_code", "ip_address")
    list_filter = ("error_code", "created_at")
    search_fields = ("merchant_request_id", "error_code", "error_message", "ip_address")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
