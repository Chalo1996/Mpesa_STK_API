import os
from functools import wraps

from django.http import JsonResponse


DEFAULT_STAFF_SIGNIN_MESSAGE = "Please sign in with a staff account to continue."


def _get_provided_api_key(request):
    # Prefer standard custom header
    provided = request.headers.get("X-API-Key")
    if provided:
        return provided.strip()

    # Allow Authorization: Bearer <key> for convenience
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return ""



def require_internal_api_key(view_func=None, *, message: str | None = None):
    def _decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            # If a staff user is logged in via Django session auth, allow access.
            user = getattr(request, "user", None)
            if user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
                return func(request, *args, **kwargs)

            required = os.getenv("INTERNAL_API_KEY")
            if not required:
                return JsonResponse({"error": "INTERNAL_API_KEY is not set"}, status=500)

            error_message = message or DEFAULT_STAFF_SIGNIN_MESSAGE

            provided = _get_provided_api_key(request)
            if not provided:
                return JsonResponse({"error": error_message}, status=401)
            if provided != required:
                return JsonResponse({"error": error_message}, status=403)

            return func(request, *args, **kwargs)

        return _wrapped

    return _decorator if view_func is None else _decorator(view_func)



def require_staff(view_func=None, *, message: str | None = None):
    def _decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return JsonResponse({"error": message or DEFAULT_STAFF_SIGNIN_MESSAGE}, status=401)
            if not getattr(user, "is_staff", False):
                return JsonResponse({"error": message or DEFAULT_STAFF_SIGNIN_MESSAGE}, status=403)
            return func(request, *args, **kwargs)

        return _wrapped

    return _decorator if view_func is None else _decorator(view_func)
