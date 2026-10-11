from django.urls import path

from reconciliation import views

urlpatterns = [
    path("line-items/", views.LineItemListView.as_view(), name="line-item-list"),
]