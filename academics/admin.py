from django.contrib import admin
from .models import Classe, Eleve, Matiere, Composante, Bareme
from core.admin_mixins import TenantAdminMixin

@admin.register(Classe)
class ClasseAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nom", "niveau", "annee")

@admin.register(Eleve)
class EleveAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("matricule", "nom", "prenom", "classe")
    search_fields = ("nom", "prenom", "matricule")

@admin.register(Matiere)
class MatiereAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nom", "ordre_affichage", "actif")

@admin.register(Composante)
class ComposanteAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nom", "matiere")

@admin.register(Bareme)
class BaremeAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("composante", "classe", "valeur_max")
