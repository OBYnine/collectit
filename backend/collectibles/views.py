from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Collection, Item, WishlistItem
from .serializers import (
    CollectionSerializer,
    CollectionDetailSerializer,
    ItemSerializer,
)


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class CollectionViewSet(viewsets.ModelViewSet):
    serializer_class = CollectionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_fields = ["is_public"]

    def get_queryset(self):
        qs = Collection.objects.all()
        owner_param = self.request.query_params.get("owner")

        if owner_param == "me":
            if self.request.user.is_authenticated:
                return qs.filter(owner=self.request.user)
            return qs.none()
        elif owner_param:
            try:
                return qs.filter(owner_id=int(owner_param), is_public=True)
            except (ValueError, TypeError):
                return qs.none()

        if self.request.user.is_authenticated:
            return qs.filter(Q(owner=self.request.user) | Q(is_public=True))
        return qs.filter(is_public=True)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CollectionDetailSerializer
        return CollectionSerializer


class ItemViewSet(viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_fields = ["collection", "is_for_sale"]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]

    def get_queryset(self):
        qs = Item.objects.select_related("owner", "collection")
        owner_param = self.request.query_params.get("owner")
        if owner_param == "me":
            if self.request.user.is_authenticated:
                return qs.filter(owner=self.request.user)
            return qs.none()
        elif owner_param:
            try:
                user_id = int(owner_param)
                # ?private_for_sale=1 — предметы из приватных коллекций, выставленные на продажу
                if self.request.query_params.get("private_for_sale"):
                    return qs.filter(owner_id=user_id, collection__is_public=False, is_for_sale=True)
                # По умолчанию — только предметы из публичных коллекций
                return qs.filter(owner_id=user_id, collection__is_public=True)
            except (ValueError, TypeError):
                return qs.none()

        visible_to_public = Q(collection__is_public=True) | Q(is_for_sale=True)
        if self.request.user.is_authenticated:
            return qs.filter(Q(owner=self.request.user) | visible_to_public)
        return qs.filter(visible_to_public)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_wishlist(request, item_id):
    visible_items = Item.objects.filter(
        Q(collection__is_public=True) | Q(is_for_sale=True) | Q(owner=request.user)
    )
    item = get_object_or_404(visible_items, id=item_id)
    witem, created = WishlistItem.objects.get_or_create(user=request.user, item=item)
    if not created:
        witem.delete()
        return Response({"liked": False})
    return Response({"liked": True})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def my_wishlist(request):
    items = Item.objects.filter(
        wishlisted_by__user=request.user
    ).select_related("owner", "collection")
    serializer = ItemSerializer(items, many=True, context={"request": request})
    return Response({"results": serializer.data})
