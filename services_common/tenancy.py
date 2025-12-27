import uuid

from django.http import JsonResponse


def _uuid_or_none(value) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def resolve_business_from_request(request, provided_business_id):
    """Resolve Business using request context.

    Resolution order:
    1) If provided_business_id is present: validate and load Business.
       - If the request is OAuth2-authenticated, bind the calling OAuth client
         to this business on first use.
       - If already bound to a different business, reject.
    2) Else, if OAuth2-authenticated: use the client's stored binding.

    Returns:
      - (business, None) on success
      - (None, JsonResponse) on error

    Notes:
    - Staff-session calls are allowed by `require_oauth2(allow_staff=True)`; in
      that case we do not auto-resolve a business and will require an explicit
      business_id.
    """

    from business_api.models import Business

    token_obj = getattr(request, "oauth2_token", None)
    app = getattr(request, "oauth2_application", None) if token_obj else None

    business_uuid = _uuid_or_none(provided_business_id)

    if business_uuid:
        business = Business.objects.filter(id=business_uuid).first()
        if not business:
            return None, JsonResponse({"error": "Invalid business_id"}, status=400)

        if app is not None:
            from business_api.models import OAuthClientBusiness

            binding = (
                OAuthClientBusiness.objects.select_related("business")
                .filter(application=app)
                .first()
            )
            if binding and binding.business_id != business.id:
                return None, JsonResponse({"error": "Client is not allowed to access this business"}, status=403)
            if not binding:
                OAuthClientBusiness.objects.create(application=app, business=business)

        return business, None

    # No explicit business_id: try derive from OAuth2 client binding.
    if app is not None:
        from business_api.models import OAuthClientBusiness

        binding = OAuthClientBusiness.objects.select_related("business").filter(application=app).first()
        if binding:
            return binding.business, None

    return None, JsonResponse(
        {"error": "business_id is required (or bind your OAuth client to a business)"},
        status=400,
    )
