# core/mixins.py

class TenantQuerysetMixin:
    def get_queryset(self):
        user = self.request.user

        qs = self.queryset

        # 🔥 SUPER ADMIN → accès total
        if user.is_superuser or user.role == "ADMIN_SAAS":
            return qs.order_by("id")

        # 🔥 USERS NORMAUX
        if not user.tenant:
            return qs.none()

        return qs.filter(tenant=user.tenant).order_by("id")