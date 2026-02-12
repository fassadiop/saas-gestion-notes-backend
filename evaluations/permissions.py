# config/evaluations/permissions.py

from rest_framework.permissions import BasePermission

class IsEnseignant(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ENSEIGNANT"

class IsDirecteur(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "DIRECTEUR"

class IsParent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "PARENT"

class IsDirecteurOuAdminTenant(BasePermission):
    """
    Autorise l'accès aux directeurs et aux admins tenant
    pour la gestion des bulletins.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ("DIRECTEUR", "ADMIN_TENANT")
        )