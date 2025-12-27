from django.urls import path

from . import views


urlpatterns = [
	path("bulk", views.bulk_create, name="b2c_bulk_create"),
	path("bulk/", views.bulk_create),
	path("single", views.single_paymentrequest, name="b2c_single_paymentrequest"),
	path("single/", views.single_paymentrequest),
	path("single/list", views.single_list, name="b2c_single_list"),
	path("single/list/", views.single_list),
	path("single/<uuid:payment_request_id>", views.single_detail, name="b2c_single_detail"),
	path("single/<uuid:payment_request_id>/", views.single_detail),
	path("callback/result", views.callback_result, name="b2c_callback_result"),
	path("callback/result/", views.callback_result),
	path("callback/timeout", views.callback_timeout, name="b2c_callback_timeout"),
	path("callback/timeout/", views.callback_timeout),
	path("bulk/list", views.bulk_list, name="b2c_bulk_list"),
	path("bulk/list/", views.bulk_list),
	path("bulk/<uuid:batch_id>", views.bulk_detail, name="b2c_bulk_detail"),
	path("bulk/<uuid:batch_id>/", views.bulk_detail),
]
