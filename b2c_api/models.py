import uuid

from django.db import models


class BulkPayoutBatch(models.Model):
	"""Represents a bulk B2C payout batch.

	This stores request intent and can later be extended to call the real M-Pesa B2C API.
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
		related_name="b2c_batches",
	)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"B2C Batch {self.id} ({self.status})"


class BulkPayoutItem(models.Model):
	batch = models.ForeignKey(BulkPayoutBatch, on_delete=models.CASCADE, related_name="items")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	recipient = models.CharField(max_length=32)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	currency = models.CharField(max_length=3, default="KES")
	product_type = models.CharField(max_length=60, blank=True, default="")
	item_reference = models.CharField(max_length=64, blank=True, default="")
	status = models.CharField(max_length=20, default="queued")
	result = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["id"]

	def __str__(self) -> str:
		return f"B2C Item {self.id} -> {self.recipient} ({self.amount} {self.currency})"


class B2CPaymentRequest(models.Model):
	"""Tracks a single B2C payment request and its callbacks.

	This persists request intent, Safaricom API responses, and callback payloads.
	"""

	STATUS_QUEUED = "queued"
	STATUS_SUBMITTED = "submitted"
	STATUS_RESULT = "result"
	STATUS_TIMEOUT = "timeout"
	STATUS_ERROR = "error"

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	business = models.ForeignKey(
		"business_api.Business",
		on_delete=models.CASCADE,
		related_name="b2c_payment_requests",
	)
	bulk_item = models.ForeignKey(
		BulkPayoutItem,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="payment_requests",
	)

	environment = models.CharField(max_length=20, blank=True, default="")

	originator_conversation_id = models.CharField(max_length=100, unique=True)
	conversation_id = models.CharField(max_length=100, blank=True, default="")
	response_code = models.CharField(max_length=50, blank=True, default="")
	response_description = models.TextField(blank=True, default="")

	status = models.CharField(max_length=20, default=STATUS_QUEUED)

	request_payload = models.JSONField(default=dict, blank=True)
	api_response_payload = models.JSONField(default=dict, blank=True)
	api_error_payload = models.JSONField(default=dict, blank=True)

	callback_result_payload = models.JSONField(default=dict, blank=True)
	callback_timeout_payload = models.JSONField(default=dict, blank=True)

	result_code = models.IntegerField(null=True, blank=True)
	result_desc = models.TextField(blank=True, default="")
	internal_status_code = models.IntegerField(null=True, blank=True)
	internal_status_message = models.TextField(blank=True, default="")
	transaction_id = models.CharField(max_length=100, blank=True, default="")
	product_type = models.CharField(max_length=60, blank=True, default="")

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"B2C PaymentRequest {self.originator_conversation_id} ({self.status})"
