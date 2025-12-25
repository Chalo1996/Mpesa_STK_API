from django.urls import path

from . import views


urlpatterns = [
	# STK push lifecycle
	path("stk/push", views.stk_push, name="c2b_stk_push"),
	path("stk/push/", views.stk_push),
	path("stk/callback", views.stk_callback, name="c2b_stk_callback"),
	path("stk/callback/", views.stk_callback),
	path("stk/error", views.stk_error, name="c2b_stk_error"),
	path("stk/error/", views.stk_error),

	# C2B URL registration and callbacks
	path("register", views.register_urls, name="c2b_register"),
	path("register/", views.register_urls),
	path("confirmation", views.confirmation, name="c2b_confirmation"),
	path("confirmation/", views.confirmation),
	path("validation", views.validation, name="c2b_validation"),
	path("validation/", views.validation),

	# Transactions (service-scoped aliases)
	path("transactions/all", views.transactions_all, name="c2b_transactions_all"),
	path("transactions/all/", views.transactions_all),
	path(
		"transactions/completed",
		views.transactions_completed,
		name="c2b_transactions_completed",
	),
	path("transactions/completed/", views.transactions_completed),
]
