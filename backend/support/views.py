from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from notifications.consumers import broadcast_to_staff, broadcast_to_user
from notifications.email import send_notification_email
from notifications.telegram import send_support_ticket_telegram
from .models import SupportMessage, SupportTicket


VALID_TOPICS = {t[0] for t in SupportTicket.TOPIC_CHOICES}
VALID_STATUSES = {s[0] for s in SupportTicket.STATUS_CHOICES}


class SupportWriteThrottle(UserRateThrottle):
    scope = "support"

    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


USER_STATUS_ORDER = Case(
    When(status=SupportTicket.STATUS_OPEN, then=Value(0)),
    When(status=SupportTicket.STATUS_ANSWERED, then=Value(1)),
    When(status=SupportTicket.STATUS_CLOSED, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)

ADMIN_STATUS_ORDER = Case(
    When(status=SupportTicket.STATUS_OPEN, then=Value(0)),
    When(status=SupportTicket.STATUS_ANSWERED, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)


def _dt(value):
    return value.isoformat() if value else None


def _notify(user, title, body):
    from notifications.models import Notification
    Notification.objects.create(user=user, title=title, body=body)
    send_notification_email(user, title, body)


def _notify_staff(title, body):
    from notifications.models import Notification
    User = get_user_model()
    staff = User.objects.filter(is_active=True, is_staff=True).only('id')
    for admin in staff:
        Notification.objects.create(user=admin, title=title, body=body)
        send_notification_email(admin, title, body)


def _serialize_message(message):
    return {
        'id': message.pk,
        'sender': {
            'id': message.sender_id,
            'username': message.sender.username,
            'email': message.sender.email,
        },
        'is_admin': message.is_admin,
        'text': message.text,
        'created_at': _dt(message.created_at),
    }


def _serialize(ticket, include_user=False):
    data = {
        'id':          ticket.pk,
        'topic':       ticket.topic,
        'topic_label': ticket.get_topic_display_ru(),
        'message':     ticket.message,
        'status':      ticket.status,
        'admin_reply': ticket.admin_reply,
        'resolved_confirmed_at': _dt(ticket.resolved_confirmed_at),
        'created_at':  _dt(ticket.created_at),
        'updated_at':  _dt(ticket.updated_at),
        'messages':    [_serialize_message(m) for m in ticket.messages.all()],
    }
    if include_user:
        data['user'] = {
            'id': ticket.user_id,
            'username': ticket.user.username,
            'email': ticket.user.email,
        }
    return data


def _broadcast_ticket_to_user(ticket):
    ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket.pk)
    broadcast_to_user(ticket.user_id, {
        'type': 'support.ticket.updated',
        'ticket': _serialize(ticket),
    })


def _broadcast_ticket_to_staff(ticket):
    ticket = SupportTicket.objects.select_related('user').prefetch_related('messages__sender').get(pk=ticket.pk)
    broadcast_to_staff({
        'type': 'support.ticket.updated',
        'ticket': _serialize(ticket, include_user=True),
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SupportWriteThrottle])
def ticket_list(request):
    if request.method == 'GET':
        tickets = (
            request.user.tickets
            .prefetch_related('messages__sender')
            .annotate(status_order=USER_STATUS_ORDER)
            .order_by('status_order', '-updated_at')
        )
        return Response([_serialize(t) for t in tickets])

    topic   = request.data.get('topic', '').strip()
    message = request.data.get('message', '').strip()
    if topic not in VALID_TOPICS:
        return Response({'detail': 'Выберите тему обращения.'}, status=status.HTTP_400_BAD_REQUEST)
    if not message:
        return Response({'detail': 'Текст обращения обязателен.'}, status=status.HTTP_400_BAD_REQUEST)

    ticket = SupportTicket.objects.create(user=request.user, topic=topic, message=message)
    SupportMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        is_admin=False,
        text=message,
    )
    _notify_staff(
        'Новое обращение в поддержку',
        f'{request.user.username}: {ticket.get_topic_display_ru()}',
    )
    send_support_ticket_telegram(ticket, event='new', message_text=message)
    _broadcast_ticket_to_staff(ticket)
    ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket.pk)
    return Response(_serialize(ticket), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SupportWriteThrottle])
def ticket_message_create(request, pk):
    try:
        ticket = request.user.tickets.get(pk=pk)
    except SupportTicket.DoesNotExist:
        return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

    if ticket.status == SupportTicket.STATUS_CLOSED:
        return Response({'detail': 'Закрытый тикет нельзя дополнить.'}, status=status.HTTP_400_BAD_REQUEST)

    message = str(request.data.get('message') or '').strip()
    if not message:
        return Response({'detail': 'Текст сообщения обязателен.'}, status=status.HTTP_400_BAD_REQUEST)

    SupportMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        is_admin=False,
        text=message,
    )
    ticket.status = SupportTicket.STATUS_OPEN
    ticket.resolved_confirmed_at = None
    ticket.save(update_fields=['status', 'resolved_confirmed_at', 'updated_at'])

    _notify_staff(
        'Пользователь дополнил обращение',
        f'{request.user.username} написал по тикету #{ticket.pk}: {ticket.get_topic_display_ru()}',
    )
    send_support_ticket_telegram(ticket, event='reply', message_text=message)
    _broadcast_ticket_to_user(ticket)
    _broadcast_ticket_to_staff(ticket)

    ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket.pk)
    return Response(_serialize(ticket), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ticket_resolve_confirm(request, pk):
    try:
        ticket = request.user.tickets.get(pk=pk)
    except SupportTicket.DoesNotExist:
        return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

    if ticket.status != SupportTicket.STATUS_CLOSED:
        return Response({'detail': 'Подтвердить решение можно только у закрытого тикета.'}, status=status.HTTP_400_BAD_REQUEST)

    if ticket.resolved_confirmed_at is None:
        ticket.resolved_confirmed_at = timezone.now()
        ticket.save(update_fields=['resolved_confirmed_at', 'updated_at'])
        _broadcast_ticket_to_user(ticket)
        _broadcast_ticket_to_staff(ticket)

    ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket.pk)
    return Response(_serialize(ticket))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_ticket_list(request):
    tickets = (
        SupportTicket.objects
        .select_related('user')
        .prefetch_related('messages__sender')
        .exclude(status=SupportTicket.STATUS_CLOSED)
        .annotate(status_order=ADMIN_STATUS_ORDER)
        .order_by('status_order', '-updated_at')
    )
    topic = request.query_params.get('topic')
    status_value = request.query_params.get('status')

    if topic in VALID_TOPICS:
        tickets = tickets.filter(topic=topic)
    if status_value in VALID_STATUSES:
        tickets = tickets.filter(status=status_value)

    return Response([_serialize(ticket, include_user=True) for ticket in tickets])


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_ticket_detail(request, pk):
    try:
        ticket = SupportTicket.objects.select_related('user').prefetch_related('messages__sender').get(pk=pk)
    except SupportTicket.DoesNotExist:
        return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

    previous_status = ticket.status
    reply = str(request.data.get('admin_reply') or '').strip() if 'admin_reply' in request.data else ''
    if reply:
        SupportMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            is_admin=True,
            text=reply,
        )
        ticket.admin_reply = reply

    status_value = request.data.get('status')
    if status_value is not None:
        if status_value not in VALID_STATUSES:
            return Response({'status': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        ticket.status = status_value
        if status_value != SupportTicket.STATUS_CLOSED:
            ticket.resolved_confirmed_at = None
    elif reply and ticket.status == SupportTicket.STATUS_OPEN:
        ticket.status = SupportTicket.STATUS_ANSWERED
        ticket.resolved_confirmed_at = None

    ticket.save(update_fields=['admin_reply', 'status', 'resolved_confirmed_at', 'updated_at'])
    if reply:
        _notify(
            ticket.user,
            'Поддержка ответила на обращение',
            f'Получен ответ по тикету #{ticket.pk}: {ticket.get_topic_display_ru()}',
        )
    if previous_status != SupportTicket.STATUS_CLOSED and ticket.status == SupportTicket.STATUS_CLOSED:
        _notify(
            ticket.user,
            'Обращение закрыто',
            f'Тикет #{ticket.pk} закрыт: {ticket.get_topic_display_ru()}',
        )
    _broadcast_ticket_to_user(ticket)
    _broadcast_ticket_to_staff(ticket)
    ticket = SupportTicket.objects.select_related('user').prefetch_related('messages__sender').get(pk=ticket.pk)
    return Response(_serialize(ticket, include_user=True))
