from rest_framework.routers import DefaultRouter
from evaluations.views import BulletinViewSet

router = DefaultRouter()
router.register("bulletins", BulletinViewSet, basename="bulletin")

urlpatterns = router.urls
