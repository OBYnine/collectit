from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SupportTicket


VALID_TOPICS = {t[0] for t in SupportTicket.TOPIC_CHOICES}


def _serialize(ticket):
    return {
        'id':          ticket.pk,
        'topic':       ticket.topic,
        'topic_label': ticket.get_topic_display_ru(),
        'message':     ticket.message,
        'status':      ticket.status,
        'admin_reply': ticket.admin_reply,
        'created_at':  ticket.created_at,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ticket_list(request):
    if request.method == 'GET':
        tickets = request.user.tickets.all()
        return Response([_serialize(t) for t in tickets])

    topic   = request.data.get('topic', '').strip()
    message = request.data.get('message', '').strip()
    if topic not in VALID_TOPICS:
        return Response({'detail': 'Выберите тему обращения.'}, status=status.HTTP_400_BAD_REQUEST)
    if not message:
        return Response({'detail': 'Текст обращения обязателен.'}, status=status.HTTP_400_BAD_REQUEST)

    ticket = SupportTicket.objects.create(user=request.user, topic=topic, message=message)
    return Response(_serialize(ticket), status=status.HTTP_201_CREATED)
