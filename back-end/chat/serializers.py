from rest_framework import serializers

from .models import Conversation, Message



class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        # The digest itself is prompt material, not screen material - the user sees the file
        # name he attached, not the table we made out of it.
        fields = ["id", "role", "content", "attachment_name", "verdict", "is_starred",
                  "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source = "messages.count", read_only = True)

    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at", "message_count"]


class StarredMessageSerializer(serializers.ModelSerializer):
    """A saved answer plus enough of its origin to get back to it."""
    conversation_id = serializers.IntegerField(source = "conversation.id", read_only = True)
    conversation_title = serializers.CharField(source = "conversation.title", read_only = True)

    # Which screen it was said on. The mentor lives in this table too, and a saved answer is
    # a pointer back to the moment it was said - so the list has to know that following this
    # one means going to the mentor rather than opening a conversation in the chat.
    is_mentor = serializers.BooleanField(source = "conversation.is_mentor", read_only = True)

    class Meta:
        model = Message
        fields = ["id", "role", "content", "conversation_id", "conversation_title",
                  "is_mentor", "starred_at", "created_at"]
