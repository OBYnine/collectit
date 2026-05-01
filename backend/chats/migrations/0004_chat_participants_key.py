import hashlib

from django.db import migrations, models


def populate_and_deduplicate(apps, schema_editor):
    Chat = apps.get_model('chats', 'Chat')
    seen_keys = {}

    for chat in Chat.objects.prefetch_related('participants').order_by('id'):
        ids = sorted(chat.participants.values_list('id', flat=True))
        if len(ids) < 2:
            chat.delete()
            continue

        subject_hash = hashlib.md5(chat.subject.encode()).hexdigest()[:16]
        key = f"{ids[0]}_{ids[1]}_{subject_hash}"

        if key in seen_keys:
            # Дубль — удаляем
            chat.delete()
        else:
            seen_keys[key] = chat.id
            chat.participants_key = key
            chat.save(update_fields=['participants_key'])


class Migration(migrations.Migration):
    atomic = False  # DDL + DML нельзя смешивать в одной транзакции в PostgreSQL

    dependencies = [
        ('chats', '0003_chat_item_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='participants_key',
            field=models.CharField(blank=True, max_length=100, default=''),
            preserve_default=False,
        ),
        migrations.RunPython(populate_and_deduplicate, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='chat',
            name='participants_key',
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
    ]
