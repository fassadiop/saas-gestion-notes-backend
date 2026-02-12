from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from core.admin_mixins import TenantAdminMixin

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "tenant", "is_active")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == "ADMIN_SAAS":
            return qs
        return qs.filter(tenant=request.tenant)

    def save_model(self, request, obj, form, change):
        if request.user.role != "ADMIN_SAAS":
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if request.user.role != "ADMIN_SAAS":
            form.base_fields["tenant"].disabled = True
        return form
