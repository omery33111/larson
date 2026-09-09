from rest_framework import serializers

from .models import Trade, TradeFile



class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = [
            "id", "executed_at", "opened_at", "symbol", "instrument", "account_id", "source_platform",
            "source_timezone",
            "outcome", "direction", "quantity", "entry_price", "exit_price", "pnl", "currency", "points", "fees",
            "r_multiple", "stop_loss", "take_profit", "duration_seconds", "orders_count",
            "setups", "tags", "mistakes", "notes", "rating", "screenshot_url",
        ]


class TradeFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeFile
        fields = [
            "id", "original_name", "source_platform", "uploaded_at",
            "row_count", "imported_count", "skipped_count", "mapped_by_model", "confirmed",
        ]
