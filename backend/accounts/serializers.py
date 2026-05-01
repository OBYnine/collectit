from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Full user profile with stats."""

    total_collections = serializers.SerializerMethodField()
    total_items       = serializers.SerializerMethodField()
    total_trades      = serializers.SerializerMethodField()

    def get_total_collections(self, obj):
        return obj.collections.count()

    def get_total_items(self, obj):
        return obj.items.count()

    def get_total_trades(self, obj):
        from chats.models import Chat
        return Chat.objects.filter(
            participants=obj,
            status=Chat.STATUS_COMPLETED,
        ).count()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "avatar", "bio", "phone",
            "is_news_editor",
            "member_since", "total_items", "total_collections",
            "total_trades", "rating", "balance",
            "delivery_city", "delivery_point_code", "delivery_point_address",
        ]
        read_only_fields = [
            "id", "member_since", "rating", "balance",
            "is_news_editor",
        ]


class UserPublicSerializer(serializers.ModelSerializer):
    """Public-facing user info (for cards, search results)."""

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "rating"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)
        return user
