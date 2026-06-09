from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import F
from django.db import models
from django.utils import timezone
import secrets
import uuid


class User(AbstractUser):
    """Extended user model for collectors."""

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    member_since = models.DateField(auto_now_add=True)

    # Stats (denormalized for performance, updated via signals/tasks)
    total_items = models.PositiveIntegerField(default=0)
    total_collections = models.PositiveIntegerField(default=0)
    total_trades = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    profile_views = models.PositiveIntegerField(default=0)

    # Roles
    is_news_editor = models.BooleanField(default=False)

    # Contact
    phone = models.CharField(max_length=20, blank=True)

    # Delivery
    delivery_city = models.CharField(max_length=200, blank=True)
    delivery_point_code = models.CharField(max_length=50, blank=True)
    delivery_point_address = models.TextField(blank=True)

    # Onboarding
    onboarding_completed_steps = models.JSONField(default=list, blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    # Legal consents
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=32, blank=True)
    personal_data_accepted_at = models.DateTimeField(null=True, blank=True)
    personal_data_version = models.CharField(max_length=32, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    consent_user_agent = models.CharField(max_length=512, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username

    def sync_onboarding_progress(self, *, save=True):
        """Persist once-completed onboarding steps without rolling them back."""
        step_order = ["phone", "delivery", "collection", "item"]
        completed = set(self.onboarding_completed_steps or [])

        phone_digits = "".join(ch for ch in (self.phone or "") if ch.isdigit())
        if len(phone_digits) >= 10:
            completed.add("phone")
        if self.delivery_point_code and self.delivery_point_address:
            completed.add("delivery")
        if self.collections.exists():
            completed.add("collection")
        if self.items.exists():
            completed.add("item")

        ordered = [step for step in step_order if step in completed]
        update_fields = []

        if ordered != (self.onboarding_completed_steps or []):
            self.onboarding_completed_steps = ordered
            update_fields.append("onboarding_completed_steps")
        if len(ordered) == len(step_order) and not self.onboarding_completed_at:
            self.onboarding_completed_at = timezone.now()
            update_fields.append("onboarding_completed_at")

        if save and update_fields:
            self.save(update_fields=update_fields)
        return ordered


class Transaction(models.Model):
    DEPOSIT = 'deposit'
    EXPENSE = 'expense'
    KIND_CHOICES = [(DEPOSIT, 'Пополнение'), (EXPENSE, 'Списание')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=300, blank=True)
    payment_yookassa_id = models.CharField(max_length=100, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        # Защита от двойного зачисления на уровне БД: одинаковый payment_yookassa_id
        # не может появиться дважды (но пустая строка для не-платёжных Tx разрешена).
        constraints = [
            models.UniqueConstraint(
                fields=['payment_yookassa_id'],
                condition=models.Q(payment_yookassa_id__gt=''),
                name='unique_yookassa_payment_id',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at'], name='tx_user_created_idx'),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount} — {self.user}"


class WithdrawalRequest(models.Model):
    METHOD_SBP = "sbp"
    METHOD_CARD = "card"
    METHOD_CHOICES = [
        (METHOD_SBP, "СБП"),
        (METHOD_CARD, "Карта"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает обработки"),
        (STATUS_PROCESSING, "В обработке"),
        (STATUS_SUCCEEDED, "Выплачено"),
        (STATUS_REJECTED, "Отклонено"),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_PROCESSING)

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdrawal_requests",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    card_number = models.CharField(max_length=32, blank=True)
    card_holder = models.CharField(max_length=200, blank=True)
    admin_note = models.TextField(blank=True)
    reserved_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reserved_withdrawals",
    )
    refund_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunded_withdrawals",
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_withdrawals",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "withdrawal_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="withdrawal_user_created_idx"),
            models.Index(fields=["status", "-created_at"], name="withdrawal_status_created_idx"),
        ]

    @property
    def card_masked(self):
        digits = "".join(ch for ch in self.card_number if ch.isdigit())
        if len(digits) < 4:
            return ""
        return f"**** **** **** {digits[-4:]}"

    @property
    def payout_details_public(self):
        if self.method == self.METHOD_SBP:
            return {
                "phone": self.phone,
                "bank_name": self.bank_name,
            }
        return {
            "card_number": self.card_masked,
            "card_holder": self.card_holder,
        }

    def mark_processing(self, actor=None):
        with db_transaction.atomic():
            withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            if withdrawal.status != self.STATUS_PENDING:
                return False, "Заявку можно взять в обработку только из статуса ожидания."
            withdrawal.status = self.STATUS_PROCESSING
            if actor and getattr(actor, "is_authenticated", False):
                withdrawal.processed_by = actor
            withdrawal.save(update_fields=["status", "processed_by", "updated_at"])
            return True, "Заявка взята в обработку."

    def mark_succeeded(self, actor=None):
        with db_transaction.atomic():
            withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            if withdrawal.status not in self.ACTIVE_STATUSES:
                return False, "Заявку нельзя отметить выплаченной из текущего статуса."
            withdrawal.status = self.STATUS_SUCCEEDED
            withdrawal.processed_at = timezone.now()
            if actor and getattr(actor, "is_authenticated", False):
                withdrawal.processed_by = actor
            withdrawal.save(update_fields=[
                "status",
                "processed_at",
                "processed_by",
                "updated_at",
            ])
            return True, "Заявка отмечена как выплаченная."

    def reject_and_refund(self, actor=None, reason="Заявка на вывод отклонена"):
        with db_transaction.atomic():
            withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            if withdrawal.status not in self.ACTIVE_STATUSES:
                return False, "Заявку нельзя отклонить из текущего статуса."

            user_model = self._meta.get_field("user").remote_field.model
            user_model.objects.filter(pk=withdrawal.user_id).update(balance=F("balance") + withdrawal.amount)
            refund_tx = Transaction.objects.create(
                user_id=withdrawal.user_id,
                kind=Transaction.DEPOSIT,
                amount=withdrawal.amount,
                description=f"{reason}: заявка {withdrawal.public_id}",
            )
            withdrawal.status = self.STATUS_REJECTED
            withdrawal.refund_transaction = refund_tx
            withdrawal.processed_at = timezone.now()
            if actor and getattr(actor, "is_authenticated", False):
                withdrawal.processed_by = actor
            withdrawal.save(update_fields=[
                "status",
                "refund_transaction",
                "processed_at",
                "processed_by",
                "updated_at",
            ])
            return True, "Заявка отклонена, сумма возвращена на баланс."

    def __str__(self):
        return f"{self.public_id} — {self.user} — {self.amount}"


def generate_email_verification_token():
    return secrets.token_urlsafe(48)


class PendingRegistration(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    password_hash = models.CharField(max_length=128)
    token = models.CharField(
        max_length=128,
        unique=True,
        default=generate_email_verification_token,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=32, blank=True)
    personal_data_accepted_at = models.DateTimeField(null=True, blank=True)
    personal_data_version = models.CharField(max_length=32, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    consent_user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        db_table = "pending_registrations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"], name="pending_reg_email_idx"),
            models.Index(fields=["username"], name="pending_reg_username_idx"),
            models.Index(fields=["token"], name="pending_reg_token_idx"),
            models.Index(fields=["expires_at"], name="pending_reg_expires_idx"),
        ]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.email} ({self.username})"
