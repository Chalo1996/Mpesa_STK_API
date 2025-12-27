from django.urls import path

from . import views


urlpatterns = [
	path("bulk", views.bulk_create, name="b2b_bulk_create"),
	path("bulk/", views.bulk_create),
	path("single", views.single_ussd_push, name="b2b_single_ussd_push"),
	path("single/", views.single_ussd_push),
	path("callback/result", views.callback_result, name="b2b_callback_result"),
	path("callback/result/", views.callback_result),
	path("bulk/list", views.bulk_list, name="b2b_bulk_list"),
	path("bulk/list/", views.bulk_list),
	path("bulk/<uuid:batch_id>", views.bulk_detail, name="b2b_bulk_detail"),
	path("bulk/<uuid:batch_id>/", views.bulk_detail),
]
