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
	item_reference = models.CharField(max_length=64, blank=True, default="")
	status = models.CharField(max_length=20, default="queued")
	result = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["id"]

	def __str__(self) -> str:
		return f"B2C Item {self.id} -> {self.recipient} ({self.amount} {self.currency})"
