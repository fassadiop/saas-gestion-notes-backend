# saas/views/tenant_viewset.py

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from core.models import Tenant
from core.serializers import TenantSerializer
from accounts.permissions import IsAdminSaaS

class TenantViewSet(ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsAdminSaaS]

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = True
        tenant.save(update_fields=["is_active"])
        return Response({"status": "activated"}, status=200)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = False
        tenant.save(update_fields=["is_active"])
        return Response({"status": "deactivated"}, status=200)