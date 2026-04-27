# accounts/services/user_scope_service.py

from datetime import date
from django.db.models import Q
from accounts.models import UserScope
from rest_framework.exceptions import PermissionDenied


def get_active_scopes(user):
    today = date.today()

    return UserScope.objects.filter(
        user=user,
        actif=True,
        date_debut__lte=today
    ).filter(
        Q(date_fin__isnull=True) |
        Q(date_fin__gte=today)
    )


def get_scope_filters(user):

    # 🔥 ADMIN NATIONAL
    if user.role == "ADMIN_NATIONAL":
        return {}

    scopes = get_active_scopes(user)

    inspection_ids = list(
        scopes.values_list("inspection_id", flat=True)
    )

    academie_ids = list(
        scopes.values_list("academie_id", flat=True)
    )

    # 🔴 CAS ADMIN_IEF SANS SCOPE → INTERDIT
    if user.role == "ADMIN_IEF" and not inspection_ids:
        raise PermissionDenied(
            "Aucune inspection assignée à cet utilisateur"
        )

    filters = {}

    if inspection_ids:
        filters["inspection_id__in"] = inspection_ids

    elif academie_ids:
        filters["inspection__academie_id__in"] = academie_ids

    else:
        # fallback UNIQUEMENT pour tenant
        if user.role == "ADMIN_TENANT":
            filters["id"] = user.tenant_id

    return filters