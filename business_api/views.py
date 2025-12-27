from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from services_common.auth import require_oauth2
from services_common.http import json_body
from services_common.tenancy import resolve_business_from_request

from .models import DarajaCredential, MpesaShortcode


def _serialize_business(b):
    return {
        "id": str(b.id),
        "name": b.name,
        "business_type": getattr(b, "business_type", ""),
        "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def _serialize_shortcode(s: MpesaShortcode):
    return {
        "id": s.id,
        "shortcode": s.shortcode,
        "shortcode_type": s.shortcode_type,
        "is_active": s.is_active,
        "lipa_passkey": "***" if (s.lipa_passkey or "").strip() else "",
        "default_account_reference_prefix": s.default_account_reference_prefix,
        "default_stk_callback_url": s.default_stk_callback_url,
        "default_ratiba_callback_url": s.default_ratiba_callback_url,
        "txn_status_initiator_name": s.txn_status_initiator_name,
        "txn_status_security_credential": "***" if (s.txn_status_security_credential or "").strip() else "",
        "txn_status_result_url": s.txn_status_result_url,
        "txn_status_timeout_url": s.txn_status_timeout_url,
        "txn_status_identifier_type": s.txn_status_identifier_type,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 8:
        return "***"
    return f"{v[:4]}***{v[-2:]}"


def _serialize_credential(c: DarajaCredential):
    return {
        "id": c.id,
        "environment": c.environment,
        "is_active": c.is_active,
        "consumer_key": _mask_secret(c.consumer_key),
        "consumer_secret": _mask_secret(c.consumer_secret),
        "token_url": c.token_url,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _resolve_business_for_request(request, *, business_id):
    business, error = resolve_business_from_request(request, business_id)
    return business, error


@require_oauth2(scopes=["business:read"])
@csrf_exempt
def onboarding(request):
    """Customer onboarding config (OAuth2-bound to a business).

    - GET: returns current business + active shortcode + active credential
    - POST: upserts business name, shortcode defaults, and Daraja credentials

    Notes:
    - OAuth callers derive their business from the bound OAuth client.
    - Staff-session callers must provide a business_id.
    """

    if request.method == "GET":
        business_id = request.GET.get("business_id")
        business, error = _resolve_business_for_request(request, business_id=business_id)
        if error:
            return error

        active_shortcode = business.shortcodes.filter(is_active=True).order_by("-created_at").first()
        active_cred = business.daraja_credentials.filter(is_active=True).order_by("-created_at").first()

        return JsonResponse(
            {
                "business": _serialize_business(business),
                "active_shortcode": _serialize_shortcode(active_shortcode) if active_shortcode else None,
                "active_daraja_credential": _serialize_credential(active_cred) if active_cred else None,
                "shortcodes": [_serialize_shortcode(s) for s in business.shortcodes.order_by("-created_at")[:50]],
                "daraja_credentials": [_serialize_credential(c) for c in business.daraja_credentials.order_by("-created_at")[:50]],
            },
            status=200,
        )

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # POST requires business:write for OAuth callers
    user = getattr(request, "user", None)
    is_staff = bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False))
    scopes = set(getattr(request, "oauth2_scopes", set()) or set())
    if not is_staff and "business:write" not in scopes:
        return JsonResponse({"error": "Insufficient scope"}, status=403)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    business, error = _resolve_business_for_request(request, business_id=payload.get("business_id"))
    if error:
        return error

    updated = {"business": False, "shortcode": False, "daraja_credential": False}

    # Business name
    business_name = str(payload.get("business_name") or payload.get("name") or "").strip()
    if business_name and business_name != business.name:
        business.name = business_name
        business.save(update_fields=["name", "updated_at"])
        updated["business"] = True

    # Business type (required if missing)
    business_type = str(payload.get("business_type") or "").strip()
    if not (getattr(business, "business_type", "") or "").strip() and not business_type:
        return JsonResponse({"error": "business_type is required"}, status=400)
    if business_type and business_type != (getattr(business, "business_type", "") or ""):
        business.business_type = business_type[:60]
        business.save(update_fields=["business_type", "updated_at"])
        updated["business"] = True

    # Shortcode defaults
    shortcode_value = str(payload.get("shortcode") or payload.get("business_shortcode") or "").strip()
    if shortcode_value:
        shortcode_type = str(payload.get("shortcode_type") or MpesaShortcode.TYPE_PAYBILL).strip() or MpesaShortcode.TYPE_PAYBILL
        if shortcode_type not in (MpesaShortcode.TYPE_PAYBILL, MpesaShortcode.TYPE_TILL):
            return JsonResponse({"error": "Invalid shortcode_type"}, status=400)

        set_active = payload.get("set_active")
        if set_active is None:
            set_active = True
        set_active = bool(set_active)

        defaults: dict[str, object] = {
            "shortcode_type": shortcode_type,
        }

        if "default_account_reference_prefix" in payload:
            defaults["default_account_reference_prefix"] = str(payload.get("default_account_reference_prefix") or "").strip()[:40]

        if "default_stk_callback_url" in payload:
            defaults["default_stk_callback_url"] = str(payload.get("default_stk_callback_url") or "").strip()

        if "default_ratiba_callback_url" in payload:
            defaults["default_ratiba_callback_url"] = str(payload.get("default_ratiba_callback_url") or "").strip()

        if "txn_status_initiator_name" in payload:
            defaults["txn_status_initiator_name"] = str(payload.get("txn_status_initiator_name") or "").strip()[:120]

        if "txn_status_security_credential" in payload:
            defaults["txn_status_security_credential"] = str(payload.get("txn_status_security_credential") or "").strip()

        if "txn_status_result_url" in payload:
            defaults["txn_status_result_url"] = str(payload.get("txn_status_result_url") or "").strip()

        if "txn_status_timeout_url" in payload:
            defaults["txn_status_timeout_url"] = str(payload.get("txn_status_timeout_url") or "").strip()

        if "txn_status_identifier_type" in payload:
            defaults["txn_status_identifier_type"] = str(payload.get("txn_status_identifier_type") or "").strip()[:8]

        if "lipa_passkey" in payload:
            defaults["lipa_passkey"] = str(payload.get("lipa_passkey") or "").strip()

        shortcode_obj, _ = MpesaShortcode.objects.update_or_create(
            business=business,
            shortcode=shortcode_value,
            defaults=defaults,
        )

        if set_active and not shortcode_obj.is_active:
            MpesaShortcode.objects.filter(business=business).exclude(id=shortcode_obj.id).update(is_active=False)
            shortcode_obj.is_active = True
            shortcode_obj.save(update_fields=["is_active", "updated_at"])

        if set_active and shortcode_obj.is_active:
            MpesaShortcode.objects.filter(business=business).exclude(id=shortcode_obj.id).update(is_active=False)

        updated["shortcode"] = True

    # Daraja credentials
    consumer_key = payload.get("consumer_key")
    consumer_secret = payload.get("consumer_secret")
    if consumer_key is not None or consumer_secret is not None:
        environment = str(payload.get("environment") or payload.get("daraja_environment") or DarajaCredential.ENV_SANDBOX).strip() or DarajaCredential.ENV_SANDBOX
        if environment not in (DarajaCredential.ENV_SANDBOX, DarajaCredential.ENV_PRODUCTION):
            return JsonResponse({"error": "Invalid environment"}, status=400)

        ck = str(consumer_key or "").strip()
        cs = str(consumer_secret or "").strip()
        if not ck or not cs:
            return JsonResponse({"error": "consumer_key and consumer_secret are required when updating credentials"}, status=400)

        token_url = str(payload.get("token_url") or "").strip()

        cred, _ = DarajaCredential.objects.update_or_create(
            business=business,
            environment=environment,
            is_active=True,
            defaults={
                "consumer_key": ck,
                "consumer_secret": cs,
                "token_url": token_url,
            },
        )
        DarajaCredential.objects.filter(business=business, environment=environment).exclude(id=cred.id).update(is_active=False)
        updated["daraja_credential"] = True

    active_shortcode = business.shortcodes.filter(is_active=True).order_by("-created_at").first()
    active_cred = business.daraja_credentials.filter(is_active=True).order_by("-created_at").first()

    return JsonResponse(
        {
            "ok": True,
            "updated": updated,
            "business": _serialize_business(business),
            "active_shortcode": _serialize_shortcode(active_shortcode) if active_shortcode else None,
            "active_daraja_credential": _serialize_credential(active_cred) if active_cred else None,
        },
        status=200,
    )
