from django.contrib import admin

from .models import RatibaOrder


@admin.register(RatibaOrder)
class RatibaOrderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "response_status")
    search_fields = ("id",)
