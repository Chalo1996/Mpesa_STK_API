from django.urls import path

from . import views


urlpatterns = [
    path("create", views.create_ratiba, name="ratiba_create"),
    path("create/", views.create_ratiba),
    path("history", views.ratiba_history, name="ratiba_history"),
    path("history/", views.ratiba_history),
    path("<uuid:order_id>", views.ratiba_detail, name="ratiba_detail"),
    path("<uuid:order_id>/", views.ratiba_detail),
]
