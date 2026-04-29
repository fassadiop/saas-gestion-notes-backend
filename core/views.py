# saas/views/tenant_viewset.py

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from core.models import Tenant
from core.serializers import TenantSerializer
from accounts.permissions import IsAdminSaaS
from core.permissions import IsAdminTenantOrDirecteur

from .models import Academie, Departement, Inspection, Region
from .serializers import AcademieSerializer, DepartementSerializer, InspectionSerializer, RegionSerializer

class TenantViewSet(ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsAdminSaaS]

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = True
        tenant.save(update_fields=["actif"])
        return Response({"status": "activated"}, status=200)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = False
        tenant.save(update_fields=["actif"])
        return Response({"status": "deactivated"}, status=200)
    
    @action(detail=False, methods=["POST"], permission_classes=[IsAdminTenantOrDirecteur])
    def upload_signature(self, request):
        tenant = request.user.tenant

        file = request.FILES.get("signature")

        if not file:
            return Response({"error": "Aucun fichier"}, status=400)

        # 🔒 Validation basique
        if not file.content_type.startswith("image/"):
            return Response({"error": "Format invalide"}, status=400)

        if file.size > 2 * 1024 * 1024:
            return Response({"error": "Fichier trop volumineux"}, status=400)

        # 🧹 supprimer ancienne signature
        if tenant.signature_directeur:
            tenant.signature_directeur.delete(save=False)

        tenant.signature_directeur = file
        tenant.save()

        return Response({
            "message": "Signature mise à jour",
            "url": tenant.signature_directeur.url
        })
    
    @action(detail=False, methods=["GET"], permission_classes=[IsAdminTenantOrDirecteur])
    def signature(self, request):
        tenant = request.user.tenant

        return Response({
            "signature_url": tenant.signature_directeur.url if tenant.signature_directeur else None
        })
    
    @action(detail=False, methods=["DELETE"], permission_classes=[IsAdminTenantOrDirecteur])
    def delete_signature(self, request):
        tenant = request.user.tenant

        if tenant.signature_directeur:
            tenant.signature_directeur.delete(save=False)
            tenant.signature_directeur = None
            tenant.save()

        return Response({"message": "Signature supprimée"})
    

class TenantModelViewSet(ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # 🔥 ADMIN SAAS → accès global
        if user.is_superuser or getattr(user, "role", None) == "ADMIN_SAAS":
            return qs.order_by("id")

        # 🔥 sécurité
        if not user.tenant:
            return qs.none()

        # 🔥 normal
        if hasattr(qs.model, "tenant"):
            return qs.filter(tenant=user.tenant).order_by("id")

        return qs.order_by("id")

    def perform_create(self, serializer):
        user = self.request.user

        if user.is_superuser or getattr(user, "role", None) == "ADMIN_SAAS":
            serializer.save()
        else:
            serializer.save(tenant=user.tenant)

    def perform_update(self, serializer):
        user = self.request.user

        if user.is_superuser or getattr(user, "role", None) == "ADMIN_SAAS":
            serializer.save()
        else:
            serializer.save(tenant=user.tenant)


class AcademieViewSet(ModelViewSet):
    queryset = Academie.objects.all().order_by("nom")
    serializer_class = AcademieSerializer
    permission_classes = [IsAuthenticated]


class InspectionViewSet(ModelViewSet):
    queryset = Inspection.objects.select_related("academie")
    serializer_class = InspectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        academie_id = self.request.query_params.get("academie")

        if academie_id:
            qs = qs.filter(academie_id=academie_id)

        return qs.order_by("nom")
    
class RegionViewSet(ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer


class DepartementViewSet(ModelViewSet):
    queryset = Departement.objects.all()
    serializer_class = DepartementSerializer
    filterset_fields = ["region"]