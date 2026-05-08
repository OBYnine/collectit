from rest_framework import serializers
from .models import Collection, Item, WishlistItem


class ItemSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    owner_avatar = serializers.ImageField(source="owner.avatar", read_only=True)
    owner_bio = serializers.CharField(source="owner.bio", read_only=True)
    is_liked = serializers.SerializerMethodField()

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.wishlisted_by.filter(user=request.user).exists()
        return False

    def validate_collection(self, value):
        request = self.context.get("request")
        if value and request and request.user.is_authenticated:
            if value.owner_id != request.user.id:
                raise serializers.ValidationError("Нельзя добавить предмет в чужую коллекцию.")
        return value

    class Meta:
        model = Item
        fields = [
            "id", "name", "description",
            "price", "currency", "is_for_sale",
            "image",
            "collection", "owner", "owner_username", "owner_avatar", "owner_bio",
            "created_at", "updated_at", "is_liked",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class CollectionSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Collection
        fields = [
            "id", "name", "description", "cover_emoji", "color",
            "is_public", "items_count", "owner", "owner_username",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class CollectionDetailSerializer(CollectionSerializer):
    items = ItemSerializer(many=True, read_only=True)

    class Meta(CollectionSerializer.Meta):
        fields = CollectionSerializer.Meta.fields + ["items"]
