from django.urls import include, path

from . import views


urlpatterns = [
    # Session auth endpoints for the dashboard (staff-only actions are enforced server-side)
    path('auth/csrf', views.auth_csrf, name='auth_csrf'),
    path('auth/me', views.auth_me, name='auth_me'),
    path('auth/login', views.auth_login, name='auth_login'),
    path('auth/logout', views.auth_logout, name='auth_logout'),

    path('access/token', views.get_access_token, name='get_mpesa_access_token'),
    path('online/lipa', views.lipa_na_mpesa_online, name='lipa_na_mpesa'),

    # Service-style aliases for the existing C2B/STK service
    path('c2b/stk/push', views.lipa_na_mpesa_online, name='c2b_stk_push'),
    path('c2b/stk/callback', views.stk_push_callback, name='c2b_stk_callback'),
    path('c2b/stk/error', views.stk_push_error, name='c2b_stk_error'),

    path('c2b/register', views.register_urls, name="register_mpesa_validation"),
    path('c2b/confirmation', views.confirmation, name="confirmation"),
    path('c2b/validation', views.validation, name="validation"),
    path('stk/callback', views.stk_push_callback, name="stk_callback"),
    path('stk/error', views.stk_push_error, name="stk_error"),
    path('transactions/all', views.all_transactions, name="get_all_transactions"),
    path('transactions/completed', views.completed_transactions, name="get_completed_transactions"),

    # Service-style aliases for C2B transactions
    path('c2b/transactions/all', views.all_transactions, name="c2b_all_transactions"),
    path('c2b/transactions/completed', views.completed_transactions, name="c2b_completed_transactions"),

    # New services
    path('b2c/', include('b2c_api.urls')),
    path('b2b/', include('b2b_api.urls')),

    # Admin-only (API key protected) log endpoints
    path('admin/logs/calls', views.admin_calls_log, name="admin_calls_log"),
    path('admin/logs/callbacks', views.admin_callbacks_log, name="admin_callbacks_log"),
    path('admin/logs/stk-errors', views.admin_stk_errors_log, name="admin_stk_errors_log"),
]
