from django.db.models import Value
from django.db.models.functions import Coalesce
from django.db.models import Count, Avg, Q, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Academie, Inspection, Tenant
from academics.models import Eleve
from evaluations.models import Bulletin, Validation

from rest_framework.exceptions import PermissionDenied
from accounts.services.user_scope_service import get_scope_filters


class DashboardIEFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        ALLOWED_ROLES = ["ADMIN_IEF", "ADMIN_TENANT", "ADMIN_NATIONAL"]

        if user.role not in ALLOWED_ROLES:
            return Response({"detail": "Accès refusé"}, status=403)

        # 🔥 NOUVEAU : filtrage intelligent
        filters = get_scope_filters(user)

        tenants = Tenant.objects.filter(**filters)

        if not tenants.exists():
            return Response(
                {"detail": "Aucune donnée disponible pour ce périmètre"},
                status=200
            )

        # 🔹 KPI
        eleves_count = Eleve.objects.filter(
            tenant__in=tenants
        ).count()

        bulletins = Bulletin.objects.filter(
            tenant__in=tenants
        )

        total_bulletins = bulletins.count()

        published_bulletins = bulletins.filter(
            statut="PUBLIE"
        ).count()

        taux_publication = (
            (published_bulletins / total_bulletins) * 100
            if total_bulletins > 0 else 0
        )

        # 🔹 WORKFLOW
        workflow = bulletins.values("statut").annotate(
            total=Count("id")
        )

        # 🔹 PERFORMANCE PAR ÉCOLE
        ecoles = bulletins.values(
            "tenant__id",
            "tenant__nom"
        ).annotate(
            nb_eleves=Count("eleve", distinct=True),
            moyenne=Avg("moyenne_sur_10"),
            taux_reussite=Count(
                "id",
                filter=Q(moyenne_sur_10__gte=5)
            ) * 100.0 / Count("id"),
            taux_publication=Count(
                "id",
                filter=Q(statut="PUBLIE")
            ) * 100.0 / Count("id")
        )

        # 🔴 ANOMALIES (optimisé)
        anomalies = []

        for tenant in tenants:
            qs = Bulletin.objects.filter(tenant=tenant)

            total = qs.count()
            published = qs.filter(statut="PUBLIE").count()
            avg = qs.aggregate(avg=Avg("moyenne_sur_10"))["avg"]

            if total > 0 and published == 0:
                anomalies.append({
                    "type": "AUCUNE_PUBLICATION",
                    "ecole": tenant.nom
                })

            if avg and avg > 9:
                anomalies.append({
                    "type": "MOYENNES_SUSPECTES",
                    "ecole": tenant.nom
                })

            if avg and avg < 3:
                anomalies.append({
                    "type": "FAIBLE_PERFORMANCE",
                    "ecole": tenant.nom
                })

        # 🔹 VALIDATIONS
        validations = Validation.objects.filter(
            tenant__in=tenants
        ).values("action").annotate(total=Count("id"))

        return Response({
            "kpis": {
                "nb_ecoles": tenants.count(),
                "nb_eleves": eleves_count,
                "nb_bulletins": total_bulletins,
                "taux_publication": round(taux_publication, 2)
            },
            "workflow": list(workflow),
            "ecoles": list(ecoles),
            "anomalies": anomalies,
            "validations": list(validations)
        })
    

class DashboardAcademieView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "ADMIN_ACADEMIE":
            raise PermissionDenied("Accès refusé")

        scope = user.scopes.filter(actif=True).first()

        if not scope or not scope.academie:
            raise PermissionDenied("Aucune académie associée")

        inspections = Inspection.objects.filter(
            academie=scope.academie
        )

        tenants = Tenant.objects.filter(
            inspection__in=inspections
        )

        # ================= KPI =================
        nb_ief = inspections.count()

        nb_ecoles = tenants.count()

        nb_eleves = Eleve.objects.filter(
            tenant__in=tenants
        ).count()

        bulletins = Bulletin.objects.filter(
            tenant__in=tenants
        )

        total_bulletins = bulletins.count()

        published_bulletins = bulletins.filter(
            statut="PUBLIE"
        ).count()

        taux_publication = (
            (published_bulletins / total_bulletins) * 100
            if total_bulletins > 0 else 0
        )

        # ================= WORKFLOW =================
        workflow = bulletins.values("statut").annotate(
            total=Count("id")
        )

        # ================= PERFORMANCE PAR IEF =================
        iefs = bulletins.values(
            "tenant__inspection__id",
            "tenant__inspection__nom"
        ).annotate(
            nb_eleves=Count("eleve", distinct=True),
            moyenne=Avg("moyenne_sur_10"),
            taux_reussite=Count(
                "id",
                filter=Q(moyenne_sur_10__gte=5)
            ) * 100.0 / Count("id"),
            taux_publication=Count(
                "id",
                filter=Q(statut="PUBLIE")
            ) * 100.0 / Count("id")
        )

        # ================= ANOMALIES =================
        anomalies = []

        for inspection in inspections:
            total = Bulletin.objects.filter(
                tenant__inspection=inspection
            ).count()

            published = Bulletin.objects.filter(
                tenant__inspection=inspection,
                statut="PUBLIE"
            ).count()

            if total > 0 and published == 0:
                anomalies.append({
                    "type": "AUCUNE_PUBLICATION",
                    "inspection": inspection.nom
                })

        # ================= VALIDATIONS =================
        validations = Validation.objects.filter(
            tenant__in=tenants
        ).values("action").annotate(total=Count("id"))

        return Response({
            "kpis": {
                "nb_ief": nb_ief,
                "nb_ecoles": nb_ecoles,
                "nb_eleves": nb_eleves,
                "taux_publication": round(taux_publication, 2)
            },
            "workflow": list(workflow),
            "iefs": list(iefs),
            "anomalies": anomalies,
            "validations": list(validations)
        })
    

class DashboardNationalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "ADMIN_NATIONAL":
            return Response({"detail": "Accès refusé"}, status=403)
        print("USER =>", user.username, user.role)
        # ================= SCOPE =================
        # ================= SCOPE =================
        if user.role != "ADMIN_NATIONAL":
            scope = user.scopes.filter(actif=True).first()

            if not scope:
                return Response({"detail": "Aucun scope actif"}, status=403)

        # ================= DATA GLOBAL =================
        academies = Academie.objects.all()

        tenants = Tenant.objects.all()

        # ================= KPI =================
        nb_academies = academies.count()
        nb_ecoles = tenants.count()

        nb_eleves = Eleve.objects.count()

        bulletins = Bulletin.objects.all()

        total_bulletins = bulletins.count()

        published_bulletins = bulletins.filter(
            statut="PUBLIE"
        ).count()

        taux_publication = (
            (published_bulletins / total_bulletins) * 100
            if total_bulletins > 0 else 0
        )

        # ================= WORKFLOW =================
        workflow = bulletins.values("statut").annotate(
            total=Count("id")
        )

        # ================= PERFORMANCE PAR ACADEMIE =================
        academies_perf = bulletins.values().annotate(
            academie_id=F("tenant__inspection__academie__id"),
            academie_nom=Coalesce(
                F("tenant__inspection__academie__nom"),
                Value("Non défini")
            ),
            nb_eleves=Count("eleve", distinct=True),
            moyenne=Avg("moyenne_sur_10"),
            taux_reussite=Count(
                "id",
                filter=Q(moyenne_sur_10__gte=5)
            ) * 100.0 / Count("id"),
            taux_publication=Count(
                "id",
                filter=Q(statut="PUBLIE")
            ) * 100.0 / Count("id")
        ).values(
            "academie_id",
            "academie_nom",
            "nb_eleves",
            "moyenne",
            "taux_reussite",
            "taux_publication"
        )

        # ================= ANOMALIES =================
        anomalies = []

        for acad in academies:
            total = Bulletin.objects.filter(
                tenant__inspection__academie=acad
            ).count()

            published = Bulletin.objects.filter(
                tenant__inspection__academie=acad,
                statut="PUBLIE"
            ).count()

            if total > 0 and published == 0:
                anomalies.append({
                    "type": "RETARD_GLOBAL",
                    "academie": acad.nom
                })

        # ================= VALIDATIONS =================
        validations = Validation.objects.values("action").annotate(
            total=Count("id")
        )

        return Response({
            "kpis": {
                "nb_academies": nb_academies,
                "nb_ecoles": nb_ecoles,
                "nb_eleves": nb_eleves,
                "taux_publication": round(taux_publication, 2)
            },
            "workflow": list(workflow),
            "academies": list(academies_perf),
            "anomalies": anomalies,
            "validations": list(validations)
        })