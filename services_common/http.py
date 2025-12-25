import datetime
import json

from django.utils import timezone


def json_body(request):
	try:
		return json.loads(request.body.decode("utf-8") or "{}")
	except Exception:
		return {}


def parse_mpesa_timestamp(value):
	if not value:
		return None
	try:
		value_str = str(value)
		# Common M-Pesa timestamp format: YYYYMMDDHHMMSS
		if len(value_str) == 14 and value_str.isdigit():
			dt = datetime.datetime.strptime(value_str, "%Y%m%d%H%M%S")
			if timezone.is_naive(dt):
				return timezone.make_aware(dt, timezone.get_current_timezone())
			return dt
	except Exception:
		return None
	return None


def parse_limit_param(request, default=200, max_limit=1000):
	raw = request.GET.get("limit", "")
	if not raw:
		return default
	try:
		value = int(raw)
		if value <= 0:
			return default
		return min(value, max_limit)
	except Exception:
		return default
