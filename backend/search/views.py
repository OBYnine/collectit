from decimal import Decimal, InvalidOperation

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from collectibles.models import Item
from collectibles.serializers import ItemSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def search_items(request):
    """
    GET /api/search/?q=монета
    """
    qs = Item.objects.filter(is_for_sale=True).select_related("owner", "collection").prefetch_related("images")

    # Исключаем предметы самого пользователя
    if request.user.is_authenticated:
        qs = qs.exclude(owner=request.user)

    q = request.query_params.get("q")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    min_price = request.query_params.get("min_price")
    if min_price:
        try:
            qs = qs.filter(price__gte=Decimal(str(min_price)))
        except InvalidOperation:
            return Response({"detail": "Некорректная минимальная цена."}, status=400)

    max_price = request.query_params.get("max_price")
    if max_price:
        try:
            qs = qs.filter(price__lte=Decimal(str(max_price)))
        except InvalidOperation:
            return Response({"detail": "Некорректная максимальная цена."}, status=400)

    if request.query_params.get("has_photo") in ("1", "true", "yes"):
        qs = qs.filter(Q(image__isnull=False, image__gt="") | Q(images__isnull=False)).distinct()

    ordering = request.query_params.get("ordering", "-created_at")
    allowed = ["price", "-price", "created_at", "-created_at"]
    if ordering in allowed:
        qs = qs.order_by(ordering)

    page_size = 20
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        return Response({"detail": "Некорректный номер страницы."}, status=400)
    start = (page - 1) * page_size
    total = qs.count()
    items = qs[start:start + page_size]
    serializer = ItemSerializer(items, many=True, context={"request": request})

    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": serializer.data,
    })
