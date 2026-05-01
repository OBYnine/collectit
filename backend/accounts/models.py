from django.contrib.auth.models import AbstractUser
from django.db import models


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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username


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
