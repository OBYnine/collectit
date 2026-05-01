from django.urls import path
from . import views

urlpatterns = [
    path("", views.search_items, name="search-items"),
]
