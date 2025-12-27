from django.urls import path

from .views import onboarding


urlpatterns = [
    path("onboarding", onboarding, name="business_onboarding"),
    path("onboarding/", onboarding),
]
