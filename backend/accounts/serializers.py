from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import PendingRegistration

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


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate(self, data):
        data["email"] = data["email"].strip().lower()
        data["username"] = data["username"].strip()

        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})
        if User.objects.filter(email__iexact=data["email"]).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже существует."})
        if User.objects.filter(username__iexact=data["username"]).exists():
            raise serializers.ValidationError({"username": "Пользователь с таким именем уже существует."})
        return data

    def create(self, validated_data):
        PendingRegistration.objects.filter(
            email__iexact=validated_data["email"],
        ).delete()
        PendingRegistration.objects.filter(
            username__iexact=validated_data["username"],
        ).delete()

        expires_at = timezone.now() + timedelta(
            hours=getattr(settings, "EMAIL_VERIFICATION_EXPIRE_HOURS", 24)
        )
        return PendingRegistration.objects.create(
            username=validated_data["username"],
            email=validated_data["email"],
            password_hash=make_password(validated_data["password"]),
            expires_at=expires_at,
        )
