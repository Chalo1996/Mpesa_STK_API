import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect

from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import AccessToken, Application

from services_common.auth import require_superuser
from services_common.http import json_body


def _serialize_app(app: Application):
    return {
        "client_id": app.client_id,
        "name": app.name,
        "client_type": app.client_type,
        "authorization_grant_type": app.authorization_grant_type,
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
