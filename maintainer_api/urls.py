from django.urls import path

from . import views

urlpatterns = [
    path("clients", views.clients, name="maintainer_clients"),
    path("clients/", views.clients),
    path("clients/<str:client_id>/rotate-secret", views.rotate_client_secret, name="maintainer_rotate_client_secret"),
    path("clients/<str:client_id>/rotate-secret/", views.rotate_client_secret),
    path("clients/<str:client_id>/revoke", views.revoke_client, name="maintainer_revoke_client"),
    path("clients/<str:client_id>/revoke/", views.revoke_client),

    # Business onboarding (maintainer-only)
    path("businesses", views.businesses, name="maintainer_businesses"),
    path("businesses/", views.businesses),
    path("businesses/<uuid:business_id>", views.business_detail, name="maintainer_business_detail"),
    path("businesses/<uuid:business_id>/", views.business_detail),
    path("businesses/<uuid:business_id>/shortcodes", views.business_shortcodes, name="maintainer_business_shortcodes"),
    path("businesses/<uuid:business_id>/shortcodes/", views.business_shortcodes),
    path(
        "businesses/<uuid:business_id>/daraja-credentials",
        views.business_daraja_credentials,
        name="maintainer_business_daraja_credentials",
    ),
    path("businesses/<uuid:business_id>/daraja-credentials/", views.business_daraja_credentials),
]
