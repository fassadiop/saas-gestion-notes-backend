class TenantAdminMixin:
    """
    Mixin Admin pour isolation multi-tenant
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.role == "ADMIN_SAAS":
            return qs

        return qs.filter(tenant=request.tenant)

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "tenant"):
            if request.user.role != "ADMIN_SAAS":
                obj.tenant = request.tenant
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "tenant" and request.user.role != "ADMIN_SAAS":
            kwargs["queryset"] = kwargs["queryset"].filter(id=request.tenant.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
