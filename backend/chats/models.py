import hashlib
import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


def _gen_track():
    """Генерирует фейковый трек-номер в формате RU + 9 цифр + RU."""
    digits = ''.join(random.choices(string.digits, k=9))
    return f"RU{digits}RU"


class Chat(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_AGREED    = 'seller_agreed'
    STATUS_PAID      = 'paid'
    STATUS_SHIPPED   = 'shipped'
    STATUS_ARRIVED   = 'arrived'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES   = [
        (STATUS_PENDING,   'Ожидание согласия'),
        (STATUS_AGREED,    'Продавец согласен'),
        (STATUS_PAID,      'Оплачено, ждём отправки'),
        (STATUS_SHIPPED,   'Посылка в пути'),
        (STATUS_ARRIVED,   'Посылка прибыла'),
        (STATUS_COMPLETED, 'Сделка завершена'),
    ]

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="chats",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="selling_chats",
    )
    item = models.ForeignKey(
        'collectibles.Item',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="chats",
    )
    subject    = models.CharField(max_length=500, blank=True)
    item_image = models.CharField(max_length=1000, blank=True)
    price      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    track_number   = models.CharField(max_length=100, blank=True)
    cdek_uuid      = models.CharField(max_length=100, blank=True)
    shipped_at     = models.DateTimeField(null=True, blank=True)
    rating         = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5, выставляет покупатель
    buyer_confirmed  = models.BooleanField(default=False)   # покупатель оценил → чат в архив
    seller_confirmed = models.BooleanField(default=False)   # продавец подтвердил → чат в архив
    # Уникальный ключ: "{min_user_id}_{max_user_id}_{md5(subject)}"
    participants_key = models.CharField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chats_chat"
        indexes = [
            # Часто фильтруем по статусу + сортируем по created_at (чат-листы, deals).
            models.Index(fields=["status", "-created_at"], name="chat_status_created_idx"),
            models.Index(fields=["seller", "status"], name="chat_seller_status_idx"),
        ]

    @classmethod
    def _make_key(cls, user_a, user_b, subject):
        lo, hi = sorted([user_a.id, user_b.id])
        subject_hash = hashlib.md5(subject.encode(), usedforsecurity=False).hexdigest()[:16]
        return f"{lo}_{hi}_{subject_hash}"

    @classmethod
    def get_or_create_between(cls, user_a, user_b, subject="", item_image="",
                               seller=None, price=None, item=None):
        key = cls._make_key(user_a, user_b, subject)
        chat, created = cls.objects.get_or_create(
            participants_key=key,
            defaults={
                "subject": subject, "item_image": item_image,
                "seller": seller, "price": price, "item": item,
            },
        )
        if created:
            chat.participants.add(user_a, user_b)
        return chat, created

    def maybe_arrive(self):
        """Если посылка отправлена > 60 сек назад — переводим в arrived."""
        if self.status == self.STATUS_SHIPPED and self.shipped_at:
            if (timezone.now() - self.shipped_at).total_seconds() >= 60:
                return True
        return False


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "chats_message"
        ordering = ["created_at"]
        indexes = [
            # Подсчёт unread (chat__participants=user, is_read=False) и сортировка.
            models.Index(fields=["chat", "is_read"], name="msg_chat_read_idx"),
            models.Index(fields=["chat", "-created_at"], name="msg_chat_created_idx"),
        ]
