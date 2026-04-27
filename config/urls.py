# config/config/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from academics.views import AdminTenantDashboardView, AffectationClasseViewSet, AnneeScolaireViewSet, ClasseViewSet, DocumentEleveViewSet, EleveViewSet, ElevesClasseEnseignantView, EnseignantDashboardView, InscriptionViewSet, MesClassesView, TenantBaremeViewSet, TenantComposanteViewSet, TenantMatiereViewSet

from core.views import AcademieViewSet, DepartementViewSet, InspectionViewSet, RegionViewSet, TenantViewSet
from accounts.views import AdminTenantViewSet, ChangePasswordView, DirecteurParentViewSet, PersonnelViewSet, UserScopeViewSet, UserViewSet
from accounts.views import MeView, ParentViewSet 
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from dashboards.views import DashboardIEFView
from evaluations.views import (
    AppreciationViewSet,
    BulletinViewSet,
    EnseignantNoteViewSet,
    ParentBulletinViewSet,
    TrimestreViewSet,
    verify_bulletin,
)

router = DefaultRouter()
router.register(r"classes", ClasseViewSet)
router.register(r"eleves", EleveViewSet,  basename="eleve")
router.register(r"users", UserViewSet)
router.register("user-scopes", UserScopeViewSet)
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
router.register(r"documents-eleves", DocumentEleveViewSet)

router.register(r"academies", AcademieViewSet)
router.register(r"inspections", InspectionViewSet)
router.register("trimestres", TrimestreViewSet, basename="trimestre")
router.register(r"inscriptions", InscriptionViewSet, basename="inscription")
router.register(r"appreciations", AppreciationViewSet)
router.register(r"regions", RegionViewSet)
router.register(r"departements", DepartementViewSet)

urlpatterns = [
    path("api/parent/", include("accounts.urls")),
    path("api/dashboard/", include("dashboards.urls")),
    path("verify/bulletin/<str:token>/", verify_bulletin),
    
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
    path("api/", include("evaluations.urls")),
    path("api/", include("accounts.urls")),
    path('api/', include('notifications.urls')),
    # AUTH
    path("api/me/", MeView.as_view(), name="me"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
