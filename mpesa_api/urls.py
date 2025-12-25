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

    # C2B service (STK + C2B callbacks + service-scoped transactions)
    path('c2b/', include('c2b_api.urls')),
    path('stk/callback', views.stk_push_callback, name="stk_callback"),
    path('stk/error', views.stk_push_error, name="stk_error"),
    path('transactions/all', views.all_transactions, name="get_all_transactions"),
    path('transactions/completed', views.completed_transactions, name="get_completed_transactions"),

    # New services
    path('b2c/', include('b2c_api.urls')),
    path('b2b/', include('b2b_api.urls')),

    # Admin-only (API key protected) log endpoints
    path('admin/logs/calls', views.admin_calls_log, name="admin_calls_log"),
    path('admin/logs/callbacks', views.admin_callbacks_log, name="admin_callbacks_log"),
    path('admin/logs/stk-errors', views.admin_stk_errors_log, name="admin_stk_errors_log"),
]
