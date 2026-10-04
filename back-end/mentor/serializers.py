from rest_framework import serializers

from .models import TraderRule


class TraderRuleSerializer(serializers.ModelSerializer):
    """An explicit field list, like every serializer here - never `__all__`."""

    class Meta:
        model = TraderRule
        fields = ["id", "kind", "number", "setups", "text", "is_active", "created_at"]

        # **`terms` is deliberately not on the list.** It is our interpretation of his
        # sentence, and showing it back would present a paraphrase of his plan as his plan -
        # he would start editing the paraphrase. He reads `text`; the loop reads `terms`.
        read_only_fields = ["id", "created_at"]
