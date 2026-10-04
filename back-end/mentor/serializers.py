from rest_framework import serializers

from .models import TraderRule


class TraderRuleSerializer(serializers.ModelSerializer):
    """An explicit field list, like every serializer here - never `__all__`."""

    class Meta:
        model = TraderRule
        fields = ["id", "kind", "number", "setups", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
