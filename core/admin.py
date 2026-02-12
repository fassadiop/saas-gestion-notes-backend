from django.contrib import admin

from academics.models import AnneeScolaire
from .models import Tenant
from .admin_mixins import TenantAdminMixin

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "actif")
    search_fields = ("nom", "code")

@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("libelle", "tenant", "actif")
