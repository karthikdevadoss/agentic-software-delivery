from django.contrib import admin

from .models import LedgerEvent


@admin.register(LedgerEvent)
class LedgerEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp_utc", "event_type", "run_id", "status", "source",
                    "provider", "model", "input_tokens", "output_tokens", "cost_usd")
    list_filter = ("event_type", "status", "source", "provider", "model", "activity_class")
    search_fields = ("run_id", "session_id", "requirement_id", "event_id")
    date_hierarchy = None  # avoids DB-specific date functions on the ledger server
    list_per_page = 50

    # Read-only by default: view permission only; every write is refused.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def get_actions(self, request):
        return {}
