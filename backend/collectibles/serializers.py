from rest_framework import serializers
from collectit.pricing import buyer_amount, service_fee_amount
from .models import Collection, Item, ItemImage, WishlistItem


TRUTHY_VALUES = ("1", "true", "yes", "on")


class ItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemImage
        fields = ["id", "image", "order"]


class ItemSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    owner_avatar = serializers.ImageField(source="owner.avatar", read_only=True)
    owner_bio = serializers.CharField(source="owner.bio", read_only=True)
    images = ItemImageSerializer(many=True, read_only=True)
    is_liked = serializers.SerializerMethodField()
    seller_price = serializers.SerializerMethodField()
    buyer_price = serializers.SerializerMethodField()
    service_fee_amount = serializers.SerializerMethodField()

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
            "price", "seller_price", "buyer_price", "service_fee_amount",
            "currency", "is_for_sale",
            "image", "images",
            "collection", "owner", "owner_username", "owner_avatar", "owner_bio",
            "created_at", "updated_at", "is_liked",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        item = super().create(validated_data)
        created_images = self._save_gallery_images(item)
        if created_images and not item.image:
            self._sync_primary_image(item)
        return item

    def get_seller_price(self, obj):
        return str(obj.price) if obj.price is not None else None

    def get_buyer_price(self, obj):
        amount = buyer_amount(obj.price)
        return str(amount) if amount is not None else None

    def get_service_fee_amount(self, obj):
        amount = service_fee_amount(obj.price)
        return str(amount) if amount is not None else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_owner = (
            request
            and request.user.is_authenticated
            and instance.owner_id == request.user.id
        )
        if not is_owner:
            data["price"] = data["buyer_price"]
        return data

    def update(self, instance, validated_data):
        item = super().update(instance, validated_data)
        request = self.context.get("request")
        if not request:
            return item

        sync_primary = False
        if self._truthy(request.data.get("replace_images", "")):
            item.images.all().delete()
            sync_primary = True

        deleted_names = self._delete_gallery_images(item)
        if deleted_names and item.image and item.image.name in deleted_names:
            sync_primary = True

        if self._truthy(request.data.get("clear_image", "")):
            item.image = ""
            item.save(update_fields=["image", "updated_at"])
            sync_primary = True

        created_images = self._save_gallery_images(item)
        if created_images and not item.image:
            sync_primary = True
        if sync_primary:
            self._sync_primary_image(item)
        return item

    def _truthy(self, value):
        return str(value).lower() in TRUTHY_VALUES

    def _delete_gallery_images(self, item):
        request = self.context.get("request")
        if not request:
            return []
        raw_ids = []
        if hasattr(request.data, "getlist"):
            raw_ids.extend(request.data.getlist("delete_image_ids"))
        value = request.data.get("delete_image_ids")
        if value and value not in raw_ids:
            raw_ids.append(value)
        ids = []
        for raw in raw_ids:
            for part in str(raw).replace(";", ",").split(","):
                part = part.strip()
                if part.isdigit():
                    ids.append(int(part))
        if not ids:
            return []
        images = list(item.images.filter(id__in=ids))
        deleted_names = [image.image.name for image in images]
        item.images.filter(id__in=[image.id for image in images]).delete()
        return deleted_names

    def _save_gallery_images(self, item):
        request = self.context.get("request")
        if not request:
            return []
        files = request.FILES.getlist("images")
        if not files:
            return []
        existing_count = item.images.count()
        created = []
        for index, file_obj in enumerate(files, start=existing_count):
            created.append(ItemImage.objects.create(item=item, image=file_obj, order=index))
        return created

    def _sync_primary_image(self, item):
        first_image = item.images.order_by("order", "id").first()
        new_name = first_image.image.name if first_image else ""
        if item.image.name != new_name:
            item.image = new_name
            item.save(update_fields=["image", "updated_at"])


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
