from rest_framework.permissions import BasePermission

class IsAdminSaaS(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "ADMIN_SAAS"
        )

class IsAdminTenant(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN_TENANT"

class IsDirecteur(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "DIRECTEUR"

class IsEnseignant(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ENSEIGNANT"

class IsParent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "PARENT"

class IsSameTenantOrAdminSaaS(BasePermission):
    """
    Protection objet : même tenant OU AdminSaaS
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role == "ADMIN_SAAS":
            return True
        return hasattr(obj, "tenant") and obj.tenant == request.tenant

class CanManageUsers(BasePermission):
    """
    ADMIN_SAAS :
      - peut créer ADMIN_TENANT
    ADMIN_TENANT :
      - peut créer Directeur, Enseignant, Parent
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.role == "ADMIN_SAAS":
            return True

        if request.user.role == "ADMIN_TENANT":
            return True

        return False


from rest_framework.permissions import BasePermission

class IsAdminTenantOrDirecteur(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ["ADMIN_TENANT", "DIRECTEUR"]
        )


class IsParent(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "PARENT"
        )
