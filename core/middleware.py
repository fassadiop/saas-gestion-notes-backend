# config/core/middleware.py

from django.http import JsonResponse

class TenantMiddleware:
    """
    Middleware SaaS :
    - n'interdit JAMAIS une requête
    - attache request.tenant si possible
    - la sécurité est gérée par DRF permissions
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            # AdminSaaS → pas de tenant
            if getattr(user, "role", None) == "ADMIN_SAAS":
                request.tenant = None
            else:
                # autres rôles → tenant si disponible
                request.tenant = getattr(user, "tenant", None)

        return self.get_response(request)

