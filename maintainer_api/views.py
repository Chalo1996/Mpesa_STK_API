import json
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect

from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import AccessToken, Application

from services_common.auth import require_superuser
from services_common.http import json_body

from business_api.models import Business, DarajaCredential, MpesaShortcode, OAuthClientBusiness


def _serialize_app(app: Application):
    binding = getattr(app, "business_binding", None)
    return {
        "client_id": app.client_id,
        "name": app.name,
        "client_type": app.client_type,
        "authorization_grant_type": app.authorization_grant_type,
        "business_id": str(binding.business_id) if binding else None,
        "created": app.created.isoformat() if getattr(app, "created", None) else None,
    }


@require_superuser
def clients(request):
    """List or create OAuth2 clients (maintainer-only).

    - GET: list existing clients
    - POST: create a new client_credentials confidential client

    Note: client_secret is only returned once on creation/rotation.
    """

    if request.method == "GET":
        apps = Application.objects.order_by("-created")[:200]
        return JsonResponse({"results": [_serialize_app(a) for a in apps]}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    business_id = payload.get("business_id")
    business = None
    if business_id:
        business = _get_business_or_404(str(business_id))
        if not business:
            return JsonResponse({"error": "Invalid business_id"}, status=400)

    client_id = generate_client_id()
    client_secret = generate_client_secret()

    app = Application.objects.create(
        user=request.user,
        name=name,
        client_id=client_id,
        client_secret=client_secret,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        skip_authorization=True,
    )

    if business:
        OAuthClientBusiness.objects.update_or_create(application=app, defaults={"business": business})

    return JsonResponse(
        {
            "client": _serialize_app(app),
            "client_secret": client_secret,
            "token_url": "/api/v1/oauth/token/",
            "grant_type": "client_credentials",
        },
        status=201,
    )


@require_superuser
def client_business(request, client_id: str):
    """Get or set the business binding for an OAuth2 client (maintainer-only)."""

    try:
        app = Application.objects.get(client_id=client_id)
    except Application.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)

    if request.method == "GET":
        binding = OAuthClientBusiness.objects.filter(application=app).first()
        return JsonResponse(
            {
                "client_id": app.client_id,
                "business_id": str(binding.business_id) if binding else None,
            },
            status=200,
        )

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    business_id = payload.get("business_id")
    if not business_id:
        return JsonResponse({"error": "business_id is required"}, status=400)

    business = _get_business_or_404(str(business_id))
    if not business:
        return JsonResponse({"error": "Invalid business_id"}, status=400)

    OAuthClientBusiness.objects.update_or_create(application=app, defaults={"business": business})

    return JsonResponse(
        {
            "client_id": app.client_id,
            "business_id": str(business.id),
            "bound": True,
        },
        status=200,
    )


@require_superuser
def rotate_client_secret(request, client_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        app = Application.objects.get(client_id=client_id)
    except Application.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)

    new_secret = generate_client_secret()

    # Revoke existing access tokens for safety.
    AccessToken.objects.filter(application=app).delete()

    app.client_secret = new_secret
    app.save(update_fields=["client_secret"])

    return JsonResponse(
        {
            "client_id": app.client_id,
            "client_secret": new_secret,
            "rotated": True,
        },
        status=200,
    )


@require_superuser
def revoke_client(request, client_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        app = Application.objects.get(client_id=client_id)
    except Application.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)

    # Delete tokens + the client record (hard revoke).
    AccessToken.objects.filter(application=app).delete()
    app.delete()

    return JsonResponse({"revoked": True, "client_id": client_id}, status=200)


def _serialize_business(b: Business):
    return {
        "id": str(b.id),
        "name": b.name,
        "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


def _serialize_shortcode(s: MpesaShortcode):
    return {
        "id": s.id,
        "shortcode": s.shortcode,
        "shortcode_type": s.shortcode_type,
        "is_active": s.is_active,
        "default_account_reference_prefix": s.default_account_reference_prefix,
        "default_stk_callback_url": s.default_stk_callback_url,
        "default_ratiba_callback_url": s.default_ratiba_callback_url,
        "txn_status_initiator_name": s.txn_status_initiator_name,
        "txn_status_security_credential": "***" if (s.txn_status_security_credential or "").strip() else "",
        "txn_status_result_url": s.txn_status_result_url,
        "txn_status_timeout_url": s.txn_status_timeout_url,
        "txn_status_identifier_type": s.txn_status_identifier_type,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
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
    }


@require_superuser
def businesses(request):
    """Maintainer-only: list or create businesses."""

    if request.method == "GET":
        items = Business.objects.order_by("-created_at")[:200]
        return JsonResponse({"results": [_serialize_business(b) for b in items]}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    business = Business.objects.create(name=name)
    return JsonResponse({"business": _serialize_business(business)}, status=201)


def _get_business_or_404(business_id: str):
    try:
        bid = uuid.UUID(str(business_id))
    except ValueError:
        return None
    return Business.objects.filter(id=bid).first()


@require_superuser
def business_detail(request, business_id: str):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    business = _get_business_or_404(business_id)
    if not business:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse(
        {
            "business": _serialize_business(business),
            "shortcodes": [_serialize_shortcode(s) for s in business.shortcodes.order_by("-created_at")[:200]],
            "daraja_credentials": [
                _serialize_credential(c) for c in business.daraja_credentials.order_by("-created_at")[:200]
            ],
        },
        status=200,
    )


@require_superuser
def business_shortcodes(request, business_id: str):
    business = _get_business_or_404(business_id)
    if not business:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        items = business.shortcodes.order_by("-created_at")[:200]
        return JsonResponse({"results": [_serialize_shortcode(s) for s in items]}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    shortcode = str(payload.get("shortcode") or "").strip()
    shortcode_type = str(payload.get("shortcode_type") or MpesaShortcode.TYPE_PAYBILL).strip() or MpesaShortcode.TYPE_PAYBILL
    lipa_passkey = str(payload.get("lipa_passkey") or "").strip()
    default_account_reference_prefix = str(payload.get("default_account_reference_prefix") or "").strip()
    default_stk_callback_url = str(payload.get("default_stk_callback_url") or "").strip()
    default_ratiba_callback_url = str(payload.get("default_ratiba_callback_url") or "").strip()

    txn_status_initiator_name = str(payload.get("txn_status_initiator_name") or "").strip()
    txn_status_security_credential = str(payload.get("txn_status_security_credential") or "").strip()
    txn_status_result_url = str(payload.get("txn_status_result_url") or "").strip()
    txn_status_timeout_url = str(payload.get("txn_status_timeout_url") or "").strip()
    txn_status_identifier_type = str(payload.get("txn_status_identifier_type") or "").strip()

    if not shortcode:
        return JsonResponse({"error": "shortcode is required"}, status=400)

    created = MpesaShortcode.objects.create(
        business=business,
        shortcode=shortcode,
        shortcode_type=shortcode_type,
        lipa_passkey=lipa_passkey,
        default_account_reference_prefix=default_account_reference_prefix,
        default_stk_callback_url=default_stk_callback_url,
        default_ratiba_callback_url=default_ratiba_callback_url,
        txn_status_initiator_name=txn_status_initiator_name,
        txn_status_security_credential=txn_status_security_credential,
        txn_status_result_url=txn_status_result_url,
        txn_status_timeout_url=txn_status_timeout_url,
        txn_status_identifier_type=txn_status_identifier_type,
    )

    return JsonResponse({"shortcode": _serialize_shortcode(created)}, status=201)


@require_superuser
def business_daraja_credentials(request, business_id: str):
    business = _get_business_or_404(business_id)
    if not business:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        items = business.daraja_credentials.order_by("-created_at")[:200]
        return JsonResponse({"results": [_serialize_credential(c) for c in items]}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json_body(request)
    if not isinstance(payload, dict):
        payload = {}

    environment = str(payload.get("environment") or DarajaCredential.ENV_SANDBOX).strip() or DarajaCredential.ENV_SANDBOX
    consumer_key = str(payload.get("consumer_key") or "").strip()
    consumer_secret = str(payload.get("consumer_secret") or "").strip()
    token_url = str(payload.get("token_url") or "").strip()

    if not consumer_key or not consumer_secret:
        return JsonResponse({"error": "consumer_key and consumer_secret are required"}, status=400)

    created = DarajaCredential.objects.create(
        business=business,
        environment=environment,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        token_url=token_url,
    )

    return JsonResponse({"credential": _serialize_credential(created)}, status=201)
