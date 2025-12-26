from django.urls import path

from . import views

urlpatterns = [
    path("clients", views.clients, name="maintainer_clients"),
    path("clients/", views.clients),
    path("clients/<str:client_id>/rotate-secret", views.rotate_client_secret, name="maintainer_rotate_client_secret"),
    path("clients/<str:client_id>/rotate-secret/", views.rotate_client_secret),
    path("clients/<str:client_id>/revoke", views.revoke_client, name="maintainer_revoke_client"),
    path("clients/<str:client_id>/revoke/", views.revoke_client),
]
