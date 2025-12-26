import os
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone


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


def _get_bearer_token(request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _get_oauth2_access_token(token: str):
    """Return DOT AccessToken object if valid & unexpired, else None."""

    if not token:
        return None

    try:
        from oauth2_provider.models import AccessToken  # type: ignore
    except Exception:
        return None

    try:
        return (
            AccessToken.objects.select_related("application")
            .filter(token=token, expires__gt=timezone.now())
            .first()
        )
    except Exception:
        return None


def _token_scopes(token_obj) -> set[str]:
    raw = (getattr(token_obj, "scope", "") or "").strip()
    return {part for part in raw.split() if part}


def _token_has_scopes(token_obj, required_scopes: list[str]) -> bool:
    if not required_scopes:
        return True

    scopes = _token_scopes(token_obj)
    return set(required_scopes).issubset(scopes)


def require_oauth2(view_func=None, *, scopes: str | list[str] | None = None, message: str | None = None, allow_staff: bool = True):
    """Require a valid OAuth2 Bearer token (optionally with scopes).

    - By default, allows logged-in staff users (session auth) for dashboard usage.
    - Does NOT accept INTERNAL_API_KEY.
    """

    required_scopes = [scopes] if isinstance(scopes, str) else (list(scopes) if scopes else [])

    def _decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            if allow_staff:
                user = getattr(request, "user", None)
                if user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
                    return func(request, *args, **kwargs)

            bearer = _get_bearer_token(request)
            if not bearer:
                return JsonResponse({"error": message or "Missing access token"}, status=401)

            token_obj = _get_oauth2_access_token(bearer)
            if not token_obj:
                return JsonResponse({"error": message or "Invalid or expired access token"}, status=401)

            if required_scopes and not _token_has_scopes(token_obj, required_scopes):
                return JsonResponse({"error": "Insufficient scope"}, status=403)

            return func(request, *args, **kwargs)

        return _wrapped

    return _decorator if view_func is None else _decorator(view_func)



def require_internal_api_key(view_func=None, *, message: str | None = None):
    def _decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            # If a staff user is logged in via Django session auth, allow access.
            user = getattr(request, "user", None)
            if user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
                return func(request, *args, **kwargs)

            # OAuth2 (client_credentials) support for third-party integrators.
            # Prefer OAuth2 Bearer tokens over treating Authorization: Bearer as an API key.
            bearer = _get_bearer_token(request)
            if bearer and _get_oauth2_access_token(bearer):
                return func(request, *args, **kwargs)

            required = os.getenv("INTERNAL_API_KEY")
            if not required:
                return JsonResponse({"error": "INTERNAL_API_KEY is not set"}, status=500)

            error_message = message or DEFAULT_STAFF_SIGNIN_MESSAGE

            # Backward compatible: allow either X-API-Key or Authorization: Bearer <INTERNAL_API_KEY>
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


def require_superuser(view_func=None, *, message: str | None = None):
    """Require a logged-in superuser (maintainer dashboard/API)."""

    def _decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return JsonResponse({"error": message or DEFAULT_STAFF_SIGNIN_MESSAGE}, status=401)
            if not getattr(user, "is_superuser", False):
                return JsonResponse({"error": message or DEFAULT_STAFF_SIGNIN_MESSAGE}, status=403)
            return func(request, *args, **kwargs)

        return _wrapped

    return _decorator if view_func is None else _decorator(view_func)
