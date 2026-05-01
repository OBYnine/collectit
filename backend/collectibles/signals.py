from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
from django.dispatch import receiver
from .models import Collection, Item


def _update_user_stats(user):
    user.total_collections = Collection.objects.filter(owner=user).count()
    user.total_items = Item.objects.filter(owner=user).count()
    user.save(update_fields=["total_collections", "total_items"])


@receiver(post_save, sender=Collection)
@receiver(post_delete, sender=Collection)
def on_collection_change(sender, instance, **kwargs):
    _update_user_stats(instance.owner)


@receiver(pre_save, sender=Item)
def on_item_pre_save(sender, instance, **kwargs):  # noqa: ARG001
    """Запоминаем старое значение is_for_sale перед сохранением."""
    if instance.pk:
        try:
            instance._old_is_for_sale = Item.objects.filter(pk=instance.pk).values_list("is_for_sale", flat=True).get()
        except Item.DoesNotExist:
            instance._old_is_for_sale = None
    else:
        instance._old_is_for_sale = None


@receiver(post_save, sender=Item)
@receiver(post_delete, sender=Item)
def on_item_change(sender, instance, **kwargs):
    _update_user_stats(instance.owner)


@receiver(post_save, sender=Item)
def on_item_sale_flag_removed(sender, instance, created, **kwargs):
    """Если is_for_sale переключили в False — убрать из вишлистов и уведомить."""
    if created:
        return
    old = getattr(instance, "_old_is_for_sale", None)
    if old is True and instance.is_for_sale is False:
        from notifications.models import Notification
        from .models import WishlistItem
        wishlist_entries = list(WishlistItem.objects.filter(item=instance).select_related("user"))
        if wishlist_entries:
            Notification.objects.bulk_create([
                Notification(
                    user=entry.user,
                    title="Предмет удалён из вишлиста",
                    body=f"Предмет «{instance.name}» был удалён или снят с продажи и больше недоступен.",
                )
                for entry in wishlist_entries
            ])
            WishlistItem.objects.filter(item=instance).delete()


@receiver(pre_delete, sender=Item)
def on_item_pre_delete(sender, instance, **kwargs):
    """Уведомить пользователей, у которых предмет был в вишлисте."""
    from notifications.models import Notification
    wishlist_entries = instance.wishlisted_by.select_related("user").all()
    notifs = [
        Notification(
            user=entry.user,
            title="Предмет удалён из вишлиста",
            body=f"Предмет «{instance.name}» был удалён или снят с продажи и больше недоступен.",
        )
        for entry in wishlist_entries
    ]
    if notifs:
        Notification.objects.bulk_create(notifs)
