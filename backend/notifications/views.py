from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_notifications(request):
    notifs = Notification.objects.filter(user=request.user)[:50]
    return Response({"results": NotificationSerializer(notifs, many=True).data})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return Response({"count": count})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"ok": True})
