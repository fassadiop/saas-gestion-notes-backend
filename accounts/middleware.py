from django.http import JsonResponse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, "must_change_password", False)
            and request.path not in [
                "/api/change-password/",
                "/api/login/",
                "/api/logout/",
            ]
        ):
            return JsonResponse(
                {"detail": "PASSWORD_CHANGE_REQUIRED"},
                status=403
            )

        return self.get_response(request)
