import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


class InternalEndpointsRateLimitMiddleware:
    """Very small fixed-window rate limiter for internal endpoints.

    - Applies to configured paths only.
    - Keyed by (client_ip, path, window).
    - Uses Django cache (default LocMemCache if not configured).

    This is intentionally simple (dev-friendly) and should be backed by a shared
    cache like Redis in multi-worker production deployments.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        enabled = bool(getattr(settings, "INTERNAL_RATE_LIMIT_ENABLED", True))
        if not enabled:
            return self.get_response(request)

        paths = getattr(settings, "INTERNAL_RATE_LIMIT_PATHS", None)
        limit = getattr(settings, "INTERNAL_RATE_LIMIT_REQUESTS", None)
        window_seconds = getattr(settings, "INTERNAL_RATE_LIMIT_WINDOW_SECONDS", None)

        # If not configured, skip (fail open).
        if not paths or not limit or not window_seconds:
            return self.get_response(request)

        try:
            paths_set = set(paths)
            limit = int(limit)
            window_seconds = int(window_seconds)
        except Exception:
            return self.get_response(request)

        if request.path not in paths_set:
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        bucket = int(time.time() // window_seconds)
        cache_key = f"internal_rl:{client_ip}:{request.path}:{bucket}"

        try:
            current = cache.get(cache_key)
            if current is None:
                cache.set(cache_key, 1, timeout=window_seconds)
                current = 1
            else:
                # cache.incr is atomic for many backends
                try:
                    current = cache.incr(cache_key)
                except Exception:
                    current = int(current) + 1
                    cache.set(cache_key, current, timeout=window_seconds)
        except Exception:
            # Fail open on cache errors.
            return self.get_response(request)

        if current > limit:
            retry_after = window_seconds - int(time.time() % window_seconds)
            response = JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
                status=429,
            )
            response["Retry-After"] = str(max(retry_after, 1))
            return response

        return self.get_response(request)

    def _get_client_ip(self, request):
        # Conservative default: REMOTE_ADDR only (avoids spoofing X-Forwarded-For).
        return request.META.get("REMOTE_ADDR") or "unknown"
