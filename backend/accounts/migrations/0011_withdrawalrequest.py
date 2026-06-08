from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_pending_registration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WithdrawalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("method", models.CharField(choices=[("sbp", "СБП"), ("card", "Карта")], max_length=10)),
                ("status", models.CharField(choices=[("pending", "Ожидает обработки"), ("processing", "В обработке"), ("succeeded", "Выплачено"), ("rejected", "Отклонено")], default="pending", max_length=20)),
                ("full_name", models.CharField(max_length=200)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("bank_name", models.CharField(blank=True, max_length=120)),
                ("card_number", models.CharField(blank=True, max_length=32)),
                ("card_holder", models.CharField(blank=True, max_length=200)),
                ("admin_note", models.TextField(blank=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processed_withdrawals", to=settings.AUTH_USER_MODEL)),
                ("refund_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="refunded_withdrawals", to="accounts.transaction")),
                ("reserved_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reserved_withdrawals", to="accounts.transaction")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="withdrawal_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "withdrawal_requests",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="withdrawal_user_created_idx"),
                    models.Index(fields=["status", "-created_at"], name="withdrawal_status_created_idx"),
                ],
            },
        ),
    ]
