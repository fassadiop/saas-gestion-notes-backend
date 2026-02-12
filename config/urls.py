from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from academics.views import AdminTenantDashboardView, AffectationClasseViewSet, AnneeScolaireViewSet, ClasseViewSet, EleveViewSet, ElevesClasseEnseignantView, EnseignantDashboardView, MesClassesView, TenantBaremeViewSet, TenantComposanteViewSet, TenantMatiereViewSet

from core.views import TenantViewSet
from accounts.views import AdminTenantViewSet, ChangePasswordView, DirecteurParentViewSet, PersonnelViewSet, UserViewSet
from accounts.views import MeView, ParentViewSet 
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from evaluations.views import (
    BulletinViewSet,
    EnseignantTrimestreViewSet,
    EnseignantNoteViewSet,
    ParentBulletinViewSet,
)

router = DefaultRouter()
router.register(r"classes", ClasseViewSet)
router.register(r"eleves", EleveViewSet,  basename="eleve")
router.register(r"users", UserViewSet)
router.register(r"annees", AnneeScolaireViewSet)
router.register("tenants", TenantViewSet, basename="tenant")
router.register("admin-tenants", AdminTenantViewSet, basename="admin-tenant")
router.register(
    "tenant/personnel",
    PersonnelViewSet,
    basename="tenant-personnel",
)
router.register(
    "tenant/matieres",
    TenantMatiereViewSet,
    basename="tenant-matieres",
)
router.register(
    "tenant/baremes",
    TenantBaremeViewSet,
    basename="tenant-baremes",
)
router.register(
    "tenant/composantes",
    TenantComposanteViewSet,
    basename="tenant-composantes",
)
router.register(
    r"affectations-classes",
    AffectationClasseViewSet,
    basename="affectation-classe",
)

router.register(
    r"enseignant/trimestres",
    EnseignantTrimestreViewSet,
    basename="enseignant-trimestres"
)

router.register(
    r"enseignant/notes",
    EnseignantNoteViewSet,
    basename="enseignant-notes"
)
router.register(
    r"bulletins",
    BulletinViewSet,
    basename="bulletin"
)
router.register(
    r"enseignant/bulletins",
    BulletinViewSet,
    basename="enseignant-bulletins"
)
router.register(
    r"parent/bulletins",
    ParentBulletinViewSet,
    basename="parent-bulletins"
)
router.register("directeur/parents", DirecteurParentViewSet, basename="directeur-parents")
router.register("parents", ParentViewSet, basename="parents")

urlpatterns = [
    
    path("api/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("admin/", admin.site.urls),

    # ENSEIGNANT
    path("api/enseignant/dashboard/", EnseignantDashboardView.as_view(), name="enseignant-dashboard"),
    path("api/enseignant/classes/", MesClassesView.as_view()),
    path(
        "api/enseignant/classes/<int:classe_id>/eleves/",
        ElevesClasseEnseignantView.as_view(),
        name="enseignant-classe-eleves",
    ),
    path("api/", include("evaluations.urls")),
    # ADMIN TENANT
    path("api/tenant/dashboard/", AdminTenantDashboardView.as_view()),
    
    # API générique
    path("api/", include(router.urls)),
    
    path("api/", include("accounts.urls")),
    # AUTH
    path("api/me/", MeView.as_view(), name="me"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
