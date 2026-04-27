# config/accounts/urls.py

from django.urls import path
from accounts.views import (
    AdminTenantViewSet,
    ChangePasswordView,
    DirecteurParentViewSet,
    ParentDashboardView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(
    r"directeur/parents",
    DirecteurParentViewSet,
    basename="directeur-parents"
)
router.register("admin-tenants", AdminTenantViewSet, basename="admin-tenants")

urlpatterns = [
    path("dashboard/", ParentDashboardView.as_view()),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]

# 🔥 fusion des routes
urlpatterns += router.urls