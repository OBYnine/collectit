from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("collections", views.CollectionViewSet, basename="collection")
router.register("items", views.ItemViewSet, basename="item")

urlpatterns = [
    path("", include(router.urls)),
    path("wishlist/", views.my_wishlist, name="my-wishlist"),
    path("wishlist/<int:item_id>/", views.toggle_wishlist, name="toggle-wishlist"),
]
