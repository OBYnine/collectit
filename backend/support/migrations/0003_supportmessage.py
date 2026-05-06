from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_ticket_text_to_messages(apps, schema_editor):
    SupportTicket = apps.get_model('support', 'SupportTicket')
    SupportMessage = apps.get_model('support', 'SupportMessage')

    messages = []
    for ticket in SupportTicket.objects.all().iterator():
        if ticket.message:
            messages.append(SupportMessage(
                ticket_id=ticket.id,
                sender_id=ticket.user_id,
                is_admin=False,
                text=ticket.message,
                created_at=ticket.created_at,
            ))
        if ticket.admin_reply:
            messages.append(SupportMessage(
                ticket_id=ticket.id,
                sender_id=ticket.user_id,
                is_admin=True,
                text=ticket.admin_reply,
                created_at=ticket.updated_at,
            ))

    SupportMessage.objects.bulk_create(messages, batch_size=500)


def delete_copied_messages(apps, schema_editor):
    SupportMessage = apps.get_model('support', 'SupportMessage')
    SupportMessage.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('support', '0002_topic_instead_of_subject'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_admin', models.BooleanField(default=False)),
                ('text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_messages', to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='support.supportticket')),
            ],
            options={
                'db_table': 'support_messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='supportmessage',
            index=models.Index(fields=['ticket', 'created_at'], name='support_msg_ticket_idx'),
        ),
        migrations.RunPython(copy_ticket_text_to_messages, delete_copied_messages),
    ]
