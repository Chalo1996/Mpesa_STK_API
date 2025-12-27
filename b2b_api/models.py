import uuid

from django.db import models


class BulkBusinessPaymentBatch(models.Model):
	"""Represents a bulk B2B payment batch.

	This stores request intent and can later be extended to call the real M-Pesa B2B API.
	"""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	reference = models.CharField(max_length=64, blank=True, default="")
	status = models.CharField(max_length=20, default="queued")
	meta = models.JSONField(default=dict, blank=True)
	last_error = models.TextField(blank=True, default="")

	business = models.ForeignKey(
		"business_api.Business",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="b2b_batches",
	)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"B2B Batch {self.id} ({self.status})"


class BulkBusinessPaymentItem(models.Model):
	batch = models.ForeignKey(BulkBusinessPaymentBatch, on_delete=models.CASCADE, related_name="items")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	recipient = models.CharField(max_length=64)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	currency = models.CharField(max_length=3, default="KES")
	product_type = models.CharField(max_length=60, blank=True, default="")
	item_reference = models.CharField(max_length=64, blank=True, default="")
	status = models.CharField(max_length=20, default="queued")
	result = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["id"]

	def __str__(self) -> str:
		return f"B2B Item {self.id} -> {self.recipient} ({self.amount} {self.currency})"


class B2BUSSDPushRequest(models.Model):
	"""Tracks a single B2B USSD push request and the resulting callback payload."""

	STATUS_QUEUED = "queued"
	STATUS_SUBMITTED = "submitted"
	STATUS_SUCCESS = "success"
	STATUS_CANCELLED = "cancelled"
	STATUS_FAILED = "failed"
	STATUS_ERROR = "error"

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	business = models.ForeignKey(
		"business_api.Business",
		on_delete=models.CASCADE,
		related_name="b2b_ussd_push_requests",
	)

	environment = models.CharField(max_length=20, blank=True, default="")

	request_ref_id = models.CharField(max_length=100, unique=True)
	response_code = models.CharField(max_length=50, blank=True, default="")
	response_status = models.TextField(blank=True, default="")

	status = models.CharField(max_length=20, default=STATUS_QUEUED)

	request_payload = models.JSONField(default=dict, blank=True)
	api_response_payload = models.JSONField(default=dict, blank=True)
	api_error_payload = models.JSONField(default=dict, blank=True)

	callback_payload = models.JSONField(default=dict, blank=True)
	result_code = models.CharField(max_length=50, blank=True, default="")
	result_desc = models.TextField(blank=True, default="")
	internal_status_code = models.IntegerField(null=True, blank=True)
	internal_status_message = models.TextField(blank=True, default="")
	amount = models.CharField(max_length=30, blank=True, default="")
	product_type = models.CharField(max_length=60, blank=True, default="")
	payment_reference = models.CharField(max_length=120, blank=True, default="")
	conversation_id = models.CharField(max_length=120, blank=True, default="")
	transaction_id = models.CharField(max_length=120, blank=True, default="")
	callback_status = models.CharField(max_length=40, blank=True, default="")

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"B2B USSD Push {self.request_ref_id} ({self.status})"
