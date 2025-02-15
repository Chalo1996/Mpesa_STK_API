from django.urls import path
from . import views


urlpatterns = [
    path('access/token', views.get_access_token, name='get_mpesa_access_token'),
    path('online/lipa', views.lipa_na_mpesa_online, name='lipa_na_mpesa'),
    path('c2b/register', views.register_urls, name="register_mpesa_validation"),
    path('c2b/confirmation', views.confirmation, name="confirmation"),
    path('c2b/validation', views.validation, name="validation"),
    path('stk/callback', views.stk_push_callback, name="stk_callback"),
    path('stk/error', views.stk_push_error, name="stk_error"),
    path('transactions/all', views.all_transactions, name="get_all_transactions"),
    path('transactions/completed', views.completed_transactions, name="get_completed_transactions"),
]
