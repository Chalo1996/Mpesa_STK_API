from django.contrib import admin

from .models import StatusCodeMapping


@admin.register(StatusCodeMapping)
class StatusCodeMappingAdmin(admin.ModelAdmin):
    list_display = ("internal_code", "external_system", "external_code", "is_success", "default_message")
    list_filter = ("external_system", "is_success")
    search_fields = ("external_code", "default_message")
    ordering = ("internal_code",)
