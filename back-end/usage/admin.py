from django.contrib import admin

from .models import TokenSpend



@admin.register(TokenSpend)
class TokenSpendAdmin(admin.ModelAdmin):
    """
    The ledger, readable without a shell.

    Read-only on purpose: these rows are a record of money that was actually spent, and a
    record somebody can edit is not a record. `usage_report` is the command that turns them
    into the figure worth looking at.
    """

    list_display = ("created_at", "user", "kind", "input_tokens", "output_tokens")
    list_filter = ("kind", "created_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj = None):
        return False
