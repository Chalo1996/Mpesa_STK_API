from django.contrib import admin

from .models import Business, BusinessMember, DarajaCredential, MpesaShortcode


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "created_at")
    search_fields = ("name", "id")
    list_filter = ("status",)


@admin.register(BusinessMember)
class BusinessMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("business__name", "user__username", "user__email")


@admin.register(DarajaCredential)
class DarajaCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "environment", "is_active", "created_at")
    list_filter = ("environment", "is_active")
    search_fields = ("business__name",)


@admin.register(MpesaShortcode)
class MpesaShortcodeAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "shortcode", "shortcode_type", "is_active", "created_at")
    list_filter = ("shortcode_type", "is_active")
    search_fields = ("shortcode", "business__name")
