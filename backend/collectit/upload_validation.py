from django.conf import settings
from rest_framework import serializers


def validate_uploaded_image(file_obj, *, field_name="image"):
    """Validate user-uploaded image before ImageField/Pillow touches storage."""
    if not file_obj:
        return file_obj

    max_bytes = getattr(settings, "USER_IMAGE_MAX_BYTES", 8 * 1024 * 1024)
    if getattr(file_obj, "size", 0) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise serializers.ValidationError({
            field_name: f"Файл слишком большой. Максимум {max_mb} МБ."
        })

    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    allowed = getattr(settings, "USER_IMAGE_ALLOWED_CONTENT_TYPES", set())
    if content_type and content_type not in allowed:
        raise serializers.ValidationError({
            field_name: "Разрешены только JPEG, PNG, WebP или GIF."
        })

    return file_obj


def validate_uploaded_image_list(files, *, existing_count=0, field_name="images"):
    max_count = getattr(settings, "USER_IMAGE_MAX_COUNT", 12)
    if existing_count + len(files) > max_count:
        raise serializers.ValidationError({
            field_name: f"Можно загрузить не больше {max_count} изображений."
        })
    for file_obj in files:
        validate_uploaded_image(file_obj, field_name=field_name)
    return files
