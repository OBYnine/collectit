from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import ipaddress
from collectit.upload_validation import validate_uploaded_image
from .models import PendingRegistration, WithdrawalRequest

User = get_user_model()
LEGAL_DOCUMENT_VERSION = "2026-06-08"


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
            "is_staff", "is_news_editor",
            "member_since", "total_items", "total_collections",
            "total_trades", "rating", "balance",
            "delivery_city", "delivery_point_code", "delivery_point_address",
            "onboarding_completed_steps", "onboarding_completed_at",
        ]
        read_only_fields = [
            "id", "member_since", "rating", "balance",
            "is_staff", "is_news_editor",
            "onboarding_completed_steps", "onboarding_completed_at",
        ]

    def validate_avatar(self, value):
        return validate_uploaded_image(value, field_name="avatar")


class UserPublicSerializer(serializers.ModelSerializer):
    """Public-facing user info (for cards, search results)."""

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "rating"]


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payout_details = serializers.SerializerMethodField()
    card_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            "id", "public_id", "amount", "method", "method_label",
            "status", "status_label", "full_name", "phone", "bank_name",
            "card_number", "card_holder", "payout_details",
            "created_at", "updated_at", "processed_at",
        ]
        read_only_fields = [
            "id", "public_id", "status", "created_at", "updated_at", "processed_at",
        ]

    def get_payout_details(self, obj):
        return obj.payout_details_public

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля.")
        if value < 100:
            raise serializers.ValidationError("Минимальная сумма вывода — 100 ₽.")
        if value > 100000:
            raise serializers.ValidationError("Максимальная сумма вывода — 100 000 ₽.")
        return value

    def validate_full_name(self, value):
        value = value.strip()
        if len(value.split()) < 2:
            raise serializers.ValidationError("Укажите фамилию и имя получателя.")
        return value

    def validate_phone(self, value):
        return value.strip()

    def validate_bank_name(self, value):
        return value.strip()

    def validate_card_holder(self, value):
        return value.strip()

    def validate_card_number(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            return ""
        if len(digits) < 13 or len(digits) > 19:
            raise serializers.ValidationError("Укажите корректный номер карты.")
        return digits

    def validate(self, data):
        method = data.get("method")
        if method == WithdrawalRequest.METHOD_SBP:
            phone = (data.get("phone") or "").strip()
            bank_name = (data.get("bank_name") or "").strip()
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) < 10:
                raise serializers.ValidationError({"phone": "Укажите телефон для СБП."})
            if not bank_name:
                raise serializers.ValidationError({"bank_name": "Укажите банк для СБП."})
            data["phone"] = phone
            data["bank_name"] = bank_name
            data["card_number"] = ""
            data["card_holder"] = ""
        elif method == WithdrawalRequest.METHOD_CARD:
            card_number = data.get("card_number") or ""
            card_holder = (data.get("card_holder") or "").strip()
            if not card_number:
                raise serializers.ValidationError({"card_number": "Укажите номер карты."})
            if not card_holder:
                raise serializers.ValidationError({"card_holder": "Укажите держателя карты."})
            data["phone"] = ""
            data["bank_name"] = ""
            data["card_holder"] = card_holder
        else:
            raise serializers.ValidationError({"method": "Выберите СБП или карту."})
        return data


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    terms_accepted = serializers.BooleanField(write_only=True)
    personal_data_accepted = serializers.BooleanField(write_only=True)

    def validate(self, data):
        data["email"] = data["email"].strip().lower()
        data["username"] = data["username"].strip()

        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})
        if data.get("terms_accepted") is not True:
            raise serializers.ValidationError({"terms_accepted": "Необходимо принять пользовательское соглашение."})
        if data.get("personal_data_accepted") is not True:
            raise serializers.ValidationError({"personal_data_accepted": "Необходимо дать согласие на обработку персональных данных."})
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
        request = self.context.get("request")
        consent_ip = None
        consent_user_agent = ""
        if request is not None:
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
            consent_ip = (forwarded_for.split(",")[0].strip() or None) if forwarded_for else request.META.get("REMOTE_ADDR")
            try:
                consent_ip = str(ipaddress.ip_address(consent_ip)) if consent_ip else None
            except ValueError:
                consent_ip = None
            consent_user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
        accepted_at = timezone.now()
        return PendingRegistration.objects.create(
            username=validated_data["username"],
            email=validated_data["email"],
            password_hash=make_password(validated_data["password"]),
            expires_at=expires_at,
            terms_accepted_at=accepted_at,
            terms_version=LEGAL_DOCUMENT_VERSION,
            personal_data_accepted_at=accepted_at,
            personal_data_version=LEGAL_DOCUMENT_VERSION,
            consent_ip=consent_ip,
            consent_user_agent=consent_user_agent,
        )
