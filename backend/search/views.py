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
    qs = Item.objects.filter(is_for_sale=True).select_related("owner", "collection")

    # Исключаем предметы самого пользователя
    if request.user.is_authenticated:
        qs = qs.exclude(owner=request.user)

    q = request.query_params.get("q")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    min_price = request.query_params.get("min_price")
    if min_price:
        qs = qs.filter(price__gte=min_price)

    max_price = request.query_params.get("max_price")
    if max_price:
        qs = qs.filter(price__lte=max_price)

    ordering = request.query_params.get("ordering", "-created_at")
    allowed = ["price", "-price", "created_at", "-created_at"]
    if ordering in allowed:
        qs = qs.order_by(ordering)

    page_size = 20
    page = int(request.query_params.get("page", 1))
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
