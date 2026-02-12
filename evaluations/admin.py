from django.contrib import admin
from .models import Trimestre, Note, Bulletin, Appreciation
from core.admin_mixins import TenantAdminMixin

@admin.register(Trimestre)
class TrimestreAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("numero", "annee")

@admin.register(Note)
class NoteAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("eleve", "composante", "valeur", "trimestre")

@admin.register(Appreciation)
class AppreciationAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("libelle", "moyenne_min", "moyenne_max")

@admin.register(Bulletin)
class BulletinAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("eleve", "trimestre", "moyenne_sur_10", "statut")
    readonly_fields = ("total_points", "total_max", "moyenne_sur_10", "rang")
