from django.db import models
from django.conf import settings


class SupportTicket(models.Model):
    STATUS_OPEN     = 'open'
    STATUS_ANSWERED = 'answered'
    STATUS_CLOSED   = 'closed'
    STATUS_CHOICES  = [
        (STATUS_OPEN,     'Открыт'),
        (STATUS_ANSWERED, 'Отвечен'),
        (STATUS_CLOSED,   'Закрыт'),
    ]

    TOPIC_SITE      = 'site'
    TOPIC_SELLER    = 'seller'
    TOPIC_BUYER     = 'buyer'
    TOPIC_PAYMENT   = 'payment'
    TOPIC_NO_MONEY  = 'no_money'
    TOPIC_CDEK      = 'cdek'
    TOPIC_DEPOSIT   = 'deposit'
    TOPIC_OTHER     = 'other'
    TOPIC_CHOICES   = [
        (TOPIC_SITE,    'Проблема с сайтом'),
        (TOPIC_SELLER,  'Проблема с продавцом'),
        (TOPIC_BUYER,   'Проблема с покупателем'),
        (TOPIC_PAYMENT, 'Проблема с оплатой'),
        (TOPIC_NO_MONEY,'Не пришли деньги'),
        (TOPIC_CDEK,    'Проблема со СДЭК'),
        (TOPIC_DEPOSIT, 'Проблема с пополнением счёта'),
        (TOPIC_OTHER,   'Другое'),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets')
    topic       = models.CharField(max_length=20, choices=TOPIC_CHOICES, default=TOPIC_OTHER)
    message     = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    admin_reply = models.TextField(blank=True)
    resolved_confirmed_at = models.DateTimeField(null=True, blank=True)

    def get_topic_display_ru(self):
        return dict(self.TOPIC_CHOICES).get(self.topic, self.topic)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'support_tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.pk} {self.get_topic_display_ru()} ({self.user})"


class SupportMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_messages')
    is_admin = models.BooleanField(default=False)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at'], name='support_msg_ticket_idx'),
        ]

    def __str__(self):
        role = 'admin' if self.is_admin else 'user'
        return f"#{self.pk} ticket={self.ticket_id} {role}"
