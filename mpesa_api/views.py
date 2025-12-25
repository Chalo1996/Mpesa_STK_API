from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie

from services_common.auth import require_staff
from services_common.http import json_body, parse_limit_param

from .models import MpesaCallBacks, MpesaCalls


def get_access_token(request):
    from c2b_api import views as c2b

    return c2b.get_access_token(request)


def register_urls(request):
    from c2b_api import views as c2b

    return c2b.register_urls(request)


def lipa_na_mpesa_online(request):
    from c2b_api import views as c2b

    return c2b.stk_push(request)


@csrf_exempt
def stk_push_callback(request):
    from c2b_api import views as c2b

    return c2b.stk_callback(request)


@csrf_exempt
def stk_push_error(request):
    from c2b_api import views as c2b

    return c2b.stk_error(request)


def completed_transactions(request):
    from c2b_api import views as c2b

    return c2b.transactions_completed(request)


def all_transactions(request):
    from c2b_api import views as c2b

    return c2b.transactions_all(request)


@ensure_csrf_cookie
def auth_csrf(request):
    """Sets CSRF cookie and returns a token for SPA usage."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    return JsonResponse({"csrfToken": get_token(request)})


def auth_me(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JsonResponse({"authenticated": False})

    return JsonResponse(
        {
            "authenticated": True,
            "username": getattr(user, "username", ""),
            "is_staff": bool(getattr(user, "is_staff", False)),
        }
    )


@csrf_protect
def auth_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json_body(request)
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))

    if not username or not password:
        return JsonResponse({"error": "Missing username or password"}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"error": "Invalid credentials"}, status=401)
    if not getattr(user, "is_staff", False):
        return JsonResponse({"error": "Please sign in with a staff account to continue."}, status=403)

    login(request, user)
    return JsonResponse({"ok": True, "username": user.username, "is_staff": True})


@csrf_protect
def auth_logout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    logout(request)
    return JsonResponse({"ok": True})


@csrf_exempt
def validation(request):
    """Legacy wrapper for /api/v1/validation."""
    from c2b_api.views import validation as impl
    return impl(request)


@csrf_exempt
def confirmation(request):
    """Legacy wrapper for /api/v1/confirmation."""
    from c2b_api.views import confirmation as impl
    return impl(request)


@require_staff
def admin_calls_log(request):
    """Admin-only: list stored M-Pesa call logs."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        limit = parse_limit_param(request)
        rows = MpesaCalls.objects.all()[:limit]
        return JsonResponse({"results": list(rows.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_staff
def admin_callbacks_log(request):
    """Admin-only: list stored M-Pesa callback payloads (STK callbacks and STK errors)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        limit = parse_limit_param(request)
        rows = MpesaCallBacks.objects.all()[:limit]
        return JsonResponse({"results": list(rows.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_staff
def admin_stk_errors_log(request):
    """Admin-only: list STK error callbacks."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        limit = parse_limit_param(request)
        rows = MpesaCallBacks.objects.filter(caller="STK Push Error")[:limit]
        return JsonResponse({"results": list(rows.values())})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)