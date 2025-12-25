from django.urls import path

from . import views


urlpatterns = [
    path("generate", views.generate_qr, name="qr_generate"),
    path("generate/", views.generate_qr),
    path("history", views.qr_history, name="qr_history"),
    path("history/", views.qr_history),
    path("<uuid:qr_id>", views.qr_detail, name="qr_detail"),
    path("<uuid:qr_id>/", views.qr_detail),
]
