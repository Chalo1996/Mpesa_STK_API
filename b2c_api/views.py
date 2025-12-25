import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from mpesa_api.views import require_internal_api_key

from .models import BulkPayoutBatch, BulkPayoutItem


def _json_body(request):
	try:
		return json.loads(request.body.decode("utf-8") or "{}")
	except Exception:
		return {}


def _serialize_batch(batch: BulkPayoutBatch):
	return {
		"id": str(batch.id),
		"created_at": batch.created_at.isoformat() if batch.created_at else None,
		"updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
		"reference": batch.reference,
		"status": batch.status,
		"items_count": batch.items.count(),
		"meta": batch.meta,
		"last_error": batch.last_error,
	}


def _serialize_item(item: BulkPayoutItem):
	return {
		"id": item.id,
		"recipient": item.recipient,
		"amount": str(item.amount),
		"currency": item.currency,
		"item_reference": item.item_reference,
		"status": item.status,
		"result": item.result,
		"created_at": item.created_at.isoformat() if item.created_at else None,
	}


@require_internal_api_key
@csrf_exempt
def bulk_create(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)

	body = _json_body(request)
	items = body.get("items")
	if not isinstance(items, list) or len(items) == 0:
		return JsonResponse({"error": "items must be a non-empty list"}, status=400)

	reference = str(body.get("reference", "")).strip()[:64]
	meta = {k: v for k, v in body.items() if k not in {"items"}}
	batch = BulkPayoutBatch.objects.create(reference=reference, meta=meta)

	created = 0
	for raw in items:
		if not isinstance(raw, dict):
			continue
		recipient = str(raw.get("recipient") or raw.get("phone_number") or "").strip()
		amount_raw = raw.get("amount")
		currency = str(raw.get("currency") or "KES").strip().upper()[:3]
		item_reference = str(raw.get("reference") or "").strip()[:64]

		if not recipient:
			continue
		try:
			amount = Decimal(str(amount_raw))
		except (InvalidOperation, TypeError):
			continue
		if amount <= 0:
			continue

		BulkPayoutItem.objects.create(
			batch=batch,
			recipient=recipient,
			amount=amount,
			currency=currency or "KES",
			item_reference=item_reference,
		)
		created += 1

	if created == 0:
		batch.delete()
		return JsonResponse({"error": "No valid items provided"}, status=400)

	return JsonResponse(
		{
			"ok": True,
			"batch": _serialize_batch(batch),
		},
		status=201,
	)


@require_internal_api_key
def bulk_list(request):
	if request.method != "GET":
		return JsonResponse({"error": "Method not allowed"}, status=405)

	try:
		limit = int(request.GET.get("limit", "50"))
	except Exception:
		limit = 50
	limit = max(1, min(limit, 200))

	qs = BulkPayoutBatch.objects.all()[:limit]
	return JsonResponse({"results": [_serialize_batch(b) for b in qs]})


@require_internal_api_key
def bulk_detail(request, batch_id):
	if request.method != "GET":
		return JsonResponse({"error": "Method not allowed"}, status=405)

	try:
		batch = BulkPayoutBatch.objects.get(id=batch_id)
	except BulkPayoutBatch.DoesNotExist:
		return JsonResponse({"error": "Not found"}, status=404)

	data = _serialize_batch(batch)
	data["items"] = [_serialize_item(i) for i in batch.items.all()]
	return JsonResponse(data)
