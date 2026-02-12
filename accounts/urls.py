from django.urls import path
from accounts.views import ChangePasswordView, DirecteurParentViewSet
from rest_framework.routers import DefaultRouter

urlpatterns = [
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]

router = DefaultRouter()
router.register(
    r"directeur/parents",
    DirecteurParentViewSet,
    basename="directeur-parents"
)

urlpatterns = router.urls