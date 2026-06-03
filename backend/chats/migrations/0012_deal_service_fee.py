from django.db import migrations, models


def copy_existing_amounts(apps, schema_editor):
    Deal = apps.get_model("chats", "Deal")
    for deal in Deal.objects.all().iterator():
        deal.buyer_amount = deal.amount
        deal.service_fee_amount = 0
        deal.save(update_fields=["buyer_amount", "service_fee_amount"])


def reset_existing_amounts(apps, schema_editor):
    Deal = apps.get_model("chats", "Deal")
    Deal.objects.update(buyer_amount=0, service_fee_amount=0)


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0011_chat_local_delete_deal_refund"),
    ]

    operations = [
        migrations.AddField(
            model_name="deal",
            name="buyer_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="deal",
            name="service_fee_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(copy_existing_amounts, reset_existing_amounts),
    ]
