from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import Chat, Message

User = get_user_model()


class ParticipantSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar"]

    def get_avatar(self, obj):
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "sender_username", "is_mine", "text", "created_at", "is_read"]

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return request and obj.sender_id == request.user.id


class ChatSerializer(serializers.ModelSerializer):
    other_participant = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    viewer_role = serializers.SerializerMethodField()
    deal_id = serializers.SerializerMethodField()
    deal_public_id = serializers.SerializerMethodField()
    support_code = serializers.SerializerMethodField()
    held_amount = serializers.SerializerMethodField()
    escrow_status = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            "id", "subject", "item_image", "price", "status", "seller_id",
            "track_number", "cdek_uuid", "shipped_at",
            "rating", "buyer_confirmed", "seller_confirmed",
            "deal_id", "deal_public_id", "support_code", "held_amount", "escrow_status",
            "viewer_role", "other_participant", "last_message", "unread_count", "created_at",
        ]

    def get_other_participant(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        other = obj.participants.exclude(pk=request.user.pk).first()
        if not other:
            return None
        return ParticipantSerializer(other, context=self.context).data

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if not msg:
            return None
        return {"text": msg.text, "created_at": str(msg.created_at)}

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=request.user).count()

    def get_viewer_role(self, obj):
        request = self.context.get("request")
        if not request or not obj.seller_id:
            return None
        return "seller" if request.user.id == obj.seller_id else "buyer"

    def get_deal_id(self, obj):
        deal = self._get_deal(obj)
        return deal.id if deal else None

    def get_deal_public_id(self, obj):
        deal = self._get_deal(obj)
        return str(deal.public_id) if deal else None

    def get_support_code(self, obj):
        return f"CHAT-{obj.pk}"

    def get_held_amount(self, obj):
        deal = self._get_deal(obj)
        return str(deal.held_amount) if deal else "0.00"

    def get_escrow_status(self, obj):
        deal = self._get_deal(obj)
        return deal.escrow_status if deal else "not_held"

    def _get_deal(self, obj):
        try:
            return obj.deal
        except ObjectDoesNotExist:
            return None
