import hashlib
import random
import string
import uuid

from django.conf import settings
from django.db import models
from django.db import transaction as db_transaction
from django.db.models import F
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
    buyer_deleted_at = models.DateTimeField(null=True, blank=True)
    seller_deleted_at = models.DateTimeField(null=True, blank=True)
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
        chat = (
            cls.objects
            .filter(participants=user_a)
            .filter(participants=user_b)
            .filter(subject=subject)
            .exclude(status=cls.STATUS_COMPLETED)
            .order_by("-created_at")
            .first()
        )
        created = False
        if not chat:
            create_key = key
            if cls.objects.filter(participants_key=create_key).exists():
                create_key = f"{key}_{uuid.uuid4().hex[:8]}"
            chat = cls.objects.create(
                participants_key=create_key,
                subject=subject,
                item_image=item_image,
                seller=seller,
                price=price,
                item=item,
            )
            created = True
        if created:
            chat.participants.add(user_a, user_b)
        if seller and price is not None:
            buyer = user_b if seller.pk == user_a.pk else user_a
            Deal.ensure_for_chat(
                chat,
                buyer=buyer,
                seller=seller,
                item=item,
                amount=price,
            )
        return chat, created

    def maybe_arrive(self):
        """Если посылка отправлена > 60 сек назад — переводим в arrived."""
        if self.status == self.STATUS_SHIPPED and self.shipped_at:
            if (timezone.now() - self.shipped_at).total_seconds() >= 60:
                return True
        return False

    def is_deleted_for(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if self.seller_id == user.id:
            return self.seller_deleted_at is not None
        return self.buyer_deleted_at is not None

    def mark_deleted_for(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return
        now = timezone.now()
        if self.seller_id == user.id:
            self.seller_deleted_at = now
            self.save(update_fields=["seller_deleted_at"])
        else:
            self.buyer_deleted_at = now
            self.save(update_fields=["buyer_deleted_at"])


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


class Deal(models.Model):
    ESCROW_NOT_HELD = "not_held"
    ESCROW_HELD = "held"
    ESCROW_RELEASED_TO_SELLER = "released_to_seller"
    ESCROW_REFUNDED_TO_BUYER = "refunded_to_buyer"
    ESCROW_CHOICES = [
        (ESCROW_NOT_HELD, "Не удержано"),
        (ESCROW_HELD, "Средства удерживаются"),
        (ESCROW_RELEASED_TO_SELLER, "Зачислено продавцу"),
        (ESCROW_REFUNDED_TO_BUYER, "Возвращено покупателю"),
    ]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    chat = models.OneToOneField(Chat, on_delete=models.CASCADE, related_name="deal")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="buying_deals",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="selling_deals",
    )
    item = models.ForeignKey(
        "collectibles.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deals",
    )
    subject = models.CharField(max_length=500, blank=True)
    item_image = models.CharField(max_length=1000, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    status = models.CharField(max_length=20, choices=Chat.STATUS_CHOICES, default=Chat.STATUS_PENDING)
    escrow_status = models.CharField(
        max_length=30,
        choices=ESCROW_CHOICES,
        default=ESCROW_NOT_HELD,
    )
    held_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="released_deals",
    )
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunded_deals",
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chats_deal"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["escrow_status", "-created_at"], name="deal_escrow_created_idx"),
            models.Index(fields=["seller", "escrow_status"], name="deal_seller_escrow_idx"),
            models.Index(fields=["buyer", "escrow_status"], name="deal_buyer_escrow_idx"),
        ]

    def __str__(self):
        return f"{self.public_id} — {self.subject or 'сделка'}"

    @classmethod
    def ensure_for_chat(cls, chat, buyer=None, seller=None, item=None, amount=None):
        if buyer is None and seller:
            buyer = chat.participants.exclude(pk=seller.pk).first()
        amount = amount if amount is not None else chat.price
        if amount is None:
            return None

        deal, _ = cls.objects.get_or_create(
            chat=chat,
            defaults={
                "buyer": buyer,
                "seller": seller or chat.seller,
                "item": item or chat.item,
                "subject": chat.subject,
                "item_image": chat.item_image,
                "amount": amount,
                "status": chat.status,
            },
        )

        update_fields = []
        updates = {
            "buyer": buyer or deal.buyer,
            "seller": seller or chat.seller or deal.seller,
            "item": item or chat.item or deal.item,
            "subject": chat.subject,
            "item_image": chat.item_image,
            "amount": amount,
            "status": chat.status,
        }
        for field, value in updates.items():
            if value is not None and getattr(deal, field) != value:
                setattr(deal, field, value)
                update_fields.append(field)
        if update_fields:
            update_fields.append("updated_at")
            deal.save(update_fields=update_fields)
        return deal

    @classmethod
    def sync_from_chat(cls, chat):
        try:
            deal = chat.deal
        except cls.DoesNotExist:
            deal = None
        if not deal:
            deal = cls.ensure_for_chat(
                chat,
                seller=chat.seller,
                item=chat.item,
                amount=chat.price,
            )
        if deal and deal.status != chat.status:
            deal.status = chat.status
            deal.save(update_fields=["status", "updated_at"])
        return deal

    def mark_held(self, amount=None):
        amount = amount if amount is not None else self.amount
        self.held_amount = amount
        self.amount = amount
        self.escrow_status = self.ESCROW_HELD
        self.paid_at = self.paid_at or timezone.now()
        self.save(update_fields=[
            "held_amount",
            "amount",
            "escrow_status",
            "paid_at",
            "updated_at",
        ])

    def can_release_to_seller(self):
        return (
            self.escrow_status == self.ESCROW_HELD
            and self.held_amount > 0
            and self.seller_id is not None
        )

    def can_refund_to_buyer(self):
        return (
            self.escrow_status == self.ESCROW_HELD
            and self.held_amount > 0
            and self.buyer_id is not None
        )

    def refund_to_buyer(self, actor=None, reason="Возврат удержанных средств покупателю"):
        from accounts.models import Transaction
        from django.contrib.auth import get_user_model

        with db_transaction.atomic():
            deal = Deal.objects.select_for_update().select_related("chat").get(pk=self.pk)
            if not deal.can_refund_to_buyer():
                return False, "Нет удержанных средств для возврата покупателю."

            amount = deal.held_amount
            UserModel = get_user_model()
            UserModel.objects.filter(pk=deal.buyer_id).update(balance=F("balance") + amount)
            Transaction.objects.create(
                user_id=deal.buyer_id,
                kind=Transaction.DEPOSIT,
                amount=amount,
                description=f"{reason}: {deal.subject or 'предмет'}",
            )

            deal.held_amount = 0
            deal.escrow_status = deal.ESCROW_REFUNDED_TO_BUYER
            deal.refunded_at = timezone.now()
            if actor and getattr(actor, "is_authenticated", False):
                deal.refunded_by = actor
            if deal.chat.status != Chat.STATUS_COMPLETED:
                deal.chat.status = Chat.STATUS_COMPLETED
                deal.chat.save(update_fields=["status"])
            deal.status = deal.chat.status
            deal.save(update_fields=[
                "held_amount",
                "escrow_status",
                "refunded_at",
                "refunded_by",
                "status",
                "updated_at",
            ])
            return True, f"{amount} ₽ возвращено покупателю."

    def release_to_seller(self, actor=None, reason="Зачисление удержанных средств продавцу"):
        from accounts.models import Transaction
        from django.contrib.auth import get_user_model

        with db_transaction.atomic():
            deal = Deal.objects.select_for_update().select_related("chat").get(pk=self.pk)
            if not deal.can_release_to_seller():
                return False, "Нет удержанных средств для зачисления продавцу."

            amount = deal.held_amount
            UserModel = get_user_model()
            UserModel.objects.filter(pk=deal.seller_id).update(balance=F("balance") + amount)
            Transaction.objects.create(
                user_id=deal.seller_id,
                kind=Transaction.DEPOSIT,
                amount=amount,
                description=f"{reason}: {deal.subject or 'предмет'}",
            )

            deal.held_amount = 0
            deal.escrow_status = deal.ESCROW_RELEASED_TO_SELLER
            deal.released_at = timezone.now()
            if actor and getattr(actor, "is_authenticated", False):
                deal.released_by = actor
            if deal.chat.status != Chat.STATUS_COMPLETED:
                deal.chat.status = Chat.STATUS_COMPLETED
                deal.chat.save(update_fields=["status"])
            deal.status = deal.chat.status
            deal.save(update_fields=[
                "held_amount",
                "escrow_status",
                "released_at",
                "released_by",
                "status",
                "updated_at",
            ])
            return True, f"{amount} ₽ зачислено продавцу."
