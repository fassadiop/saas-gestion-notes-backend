# config/evaluations/urls.py

from rest_framework.routers import DefaultRouter
from django.urls import path
from core.views import AcademieViewSet, InspectionViewSet
from evaluations.views import BulletinViewSet, TrimestreViewSet, verify_bulletin

router = DefaultRouter()
router.register("bulletins", BulletinViewSet, basename="bulletin")

urlpatterns = [
    *router.urls,

    # 🔥 QR VERIFICATION (AJOUT ICI)
    path("verify/bulletin/<str:token>/", verify_bulletin),
]