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
	item_reference = models.CharField(max_length=64, blank=True, default="")
	status = models.CharField(max_length=20, default="queued")
	result = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["id"]

	def __str__(self) -> str:
		return f"B2B Item {self.id} -> {self.recipient} ({self.amount} {self.currency})"
