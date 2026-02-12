# academics/views.py

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from accounts.permissions import IsAdminTenant, IsEnseignant
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminTenantOrDirecteur
from .models import AffectationClasse, AnneeScolaire, Eleve, Classe, Matiere, AffectationEnseignant, Bareme, Composante
from .serializers import AffectationClasseSerializer, AnneeScolaireSerializer, EleveSerializer, ClasseSerializer, ComposanteSerializer, ClasseDashboardSerializer
from accounts.models import User
from academics.serializers import MatiereSerializer, BaremeSerializer
from .services.affectations import est_enseignant_affecte_a_classe
from rest_framework.exceptions import ValidationError


class TenantFilteredViewSet(ModelViewSet):
    """
    Base ViewSet SaaS :
    - filtre automatiquement par tenant
    - injecte le tenant à la création
    """

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "ADMIN_SAAS":
            return qs
        return qs.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        if self.request.user.role != "ADMIN_SAAS":
            serializer.save(tenant=self.request.tenant)
        else:
            serializer.save()

class TenantScopedViewSet(ModelViewSet):
    """
    Base ViewSet pour données métiers tenant-scopées
    """

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(tenant=user.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

class ClasseViewSet(TenantScopedViewSet):
    queryset = Classe.objects.select_related("annee")
    serializer_class = ClasseSerializer
    permission_classes = [IsAuthenticated, IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Classe.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("annee")

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        classe = self.get_object()
        classe.actif = True
        classe.save(update_fields=["actif"])
        return Response({"status": "active"}, status=200)

    @action(detail=True, methods=["post"])
    def desactiver(self, request, pk=None):
        classe = self.get_object()
        classe.actif = False
        classe.save(update_fields=["actif"])
        return Response({"status": "inactive"}, status=200)


class EleveViewSet(TenantScopedViewSet):
    serializer_class = EleveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Eleve.objects.filter(tenant=user.tenant)

        classe_id = self.request.query_params.get("classe")

        if user.role == "ENSEIGNANT":
            if not classe_id:
                return Eleve.objects.none()

            if not est_enseignant_affecte_a_classe(
                enseignant=user,
                classe_id=classe_id,
                tenant=user.tenant,
            ):
                return Eleve.objects.none()

            return qs.filter(classe_id=classe_id)

        if classe_id:
            return qs.filter(classe_id=classe_id)

        return qs


class AdminTenantDashboardView(APIView):
    permission_classes = [IsAdminTenant]

    def get(self, request):
        tenant = request.user.tenant

        data = {
            "enseignants": User.objects.filter(
                tenant=tenant,
                role="ENSEIGNANT"
            ).count(),
            "eleves": Eleve.objects.filter(
                classe__tenant=tenant
            ).count(),
            "classes": Classe.objects.filter(
                tenant=tenant
            ).count(),
            "annee_active": AnneeScolaire.objects.filter(
                tenant=tenant,
                actif=True
            ).values("id", "libelle").first(),
        }

        return Response(data)

class AnneeScolaireViewSet(TenantScopedViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        annee = self.get_object()

        # Désactiver toutes les autres années du tenant
        AnneeScolaire.objects.filter(
            tenant=request.user.tenant
        ).exclude(id=annee.id).update(actif=False)

        annee.actif = True
        annee.save(update_fields=["actif"])

        return Response(
            {"status": "annee activee"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def desactiver(self, request, pk=None):
        annee = self.get_object()
        annee.actif = False
        annee.save(update_fields=["actif"])

        return Response(
            {"status": "annee desactivee"},
            status=status.HTTP_200_OK
        )



class TenantMatiereViewSet(ModelViewSet):
    serializer_class = MatiereSerializer
    permission_classes = [IsAuthenticated, IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Matiere.objects.filter(
            tenant=self.request.user.tenant
        ).order_by("ordre_affichage")

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="composantes"
    )
    def composantes(self, request, pk=None):
        matiere = self.get_object()

        composantes = Composante.objects.filter(
            matiere=matiere,
            tenant=request.user.tenant
        )

        serializer = ComposanteSerializer(
            composantes,
            many=True
        )
        return Response(serializer.data)
    
    @action(
        detail=True,
        methods=["post"],
        url_path="affecter_bareme"
    )
    def affecter_bareme(self, request, pk=None):
        matiere = self.get_object()
        tenant = request.user.tenant

        classe_id = request.data.get("classe")
        annee_id = request.data.get("annee")
        valeur_max = request.data.get("valeur_max")

        if not all([classe_id, annee_id, valeur_max]):
            return Response(
                {"detail": "classe, annee et valeur_max requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # =========================
        # CAS 1 — MATIÈRE DIRECTE
        # =========================
        if matiere.type_evaluation == "DIRECTE":
            bareme, created = Bareme.objects.get_or_create(
                tenant=tenant,
                matiere=matiere,
                classe_id=classe_id,
                annee_id=annee_id,
                defaults={"valeur_max": valeur_max},
            )

        # =========================
        # CAS 2 — PAR COMPOSANTE
        # =========================
        else:
            composante_id = request.data.get("composante")

            if not composante_id:
                return Response(
                    {
                        "detail": (
                            "composante requise pour une matière "
                            "évaluée par composante."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            composante = get_object_or_404(
                Composante,
                id=composante_id,
                matiere=matiere,
                tenant=tenant,
            )

            bareme, created = Bareme.objects.get_or_create(
                tenant=tenant,
                composante=composante,
                classe_id=classe_id,
                annee_id=annee_id,
                defaults={"valeur_max": valeur_max},
            )

        if not created:
            bareme.valeur_max = valeur_max
            bareme.save(update_fields=["valeur_max"])

        return Response(
            BaremeSerializer(bareme).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        matiere = self.get_object()
        matiere.actif = True
        matiere.save(update_fields=["actif"])
        return Response({"status": "active"}, status=200)

    @action(detail=True, methods=["post"])
    def desactiver(self, request, pk=None):
        matiere = self.get_object()
        matiere.actif = False
        matiere.save(update_fields=["actif"])
        return Response({"status": "inactive"}, status=200)

# class TenantBaremeViewSet(ModelViewSet):
#     serializer_class = BaremeSerializer
#     permission_classes = [IsAdminTenantOrDirecteur]

#     def get_queryset(self):
#         return (
#             Bareme.objects.filter(
#                 tenant=self.request.user.tenant
#             )
#             .select_related(
#                 "classe",
#                 "annee",
#                 "composante",
#                 "composante__matiere",
#             )
#         )

#     def perform_create(self, serializer):
#         serializer.save(tenant=self.request.user.tenant)

#     def perform_destroy(self, instance):
#         # 🔒 Interdiction si des notes existent
#         if instance.composante.note_set.exists():
#             raise ValidationError(
#                 "Impossible de supprimer un barème utilisé."
#             )
#         instance.delete()

class TenantBaremeViewSet(ModelViewSet):
    serializer_class = BaremeSerializer
    permission_classes = [IsAdminTenantOrDirecteur]
    pagination_class = None

    def get_queryset(self):
        qs = Bareme.objects.filter(
            tenant=self.request.user.tenant
        ).select_related(
            "classe",
            "annee",
            "matiere",
            "composante",
            "composante__matiere",
        )

        # 🔎 filtres UI
        classe_id = self.request.query_params.get("classe")
        annee_id = self.request.query_params.get("annee")
        composante_id = self.request.query_params.get("composante")

        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        if annee_id:
            qs = qs.filter(annee_id=annee_id)
        if composante_id:
            qs = qs.filter(composante_id=composante_id)

        return qs

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        data = serializer.validated_data

        matiere = data.get("matiere")
        composante = data.get("composante")
        classe = data.get("classe")
        annee = data.get("annee")
        valeur_max = data.get("valeur_max")

        # =========================
        # VALIDATIONS STRUCTURELLES
        # =========================
        if matiere and composante:
            raise ValidationError(
                "Barème invalide : matière et composante fournies."
            )

        if not matiere and not composante:
            raise ValidationError(
                "Barème invalide : aucune cible fournie."
            )

        # =========================
        # CAS MATIÈRE DIRECTE
        # =========================
        if matiere and not composante:
            # 🔑 forcer une composante technique
            composante = matiere.composante_set.filter(
                tenant=tenant
            ).first()

            if not composante:
                composante = Composante.objects.create(
                    tenant=tenant,
                    matiere=matiere,
                    nom="Note globale",
                    type="RESSOURCE",
                )

            bareme, created = Bareme.objects.get_or_create(
                tenant=tenant,
                classe=classe,
                annee=annee,
                composante=composante,
                defaults={"valeur_max": valeur_max},
            )

        # =========================
        # CAS PAR COMPOSANTE
        # =========================
        else:
            bareme, created = Bareme.objects.get_or_create(
                tenant=tenant,
                classe=classe,
                annee=annee,
                composante=composante,
                defaults={"valeur_max": valeur_max},
            )

        if not created:
            bareme.valeur_max = valeur_max
            bareme.save(update_fields=["valeur_max"])



class TenantComposanteViewSet(ModelViewSet):
    serializer_class = ComposanteSerializer
    permission_classes = [IsAdminTenantOrDirecteur]

    def get_queryset(self):
        qs = Composante.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("matiere")

        matiere_id = self.request.query_params.get("matiere")
        if matiere_id:
            qs = qs.filter(matiere_id=matiere_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        # 🔒 Protection métier
        if instance.note_set.exists():
            raise ValidationError(
                "Impossible de supprimer une composante déjà utilisée."
            )
        instance.delete()


class AffectationClasseViewSet(ModelViewSet):
    serializer_class = AffectationClasseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AffectationClasse.objects.filter(
            tenant=user.tenant
        )

        # 🔐 Enseignant : lecture de SES affectations uniquement
        if user.role == "ENSEIGNANT":
            return qs.filter(enseignant=user)

        # 🔐 Admin tenant : filtrage optionnel
        enseignant_id = self.request.query_params.get("enseignant")
        if enseignant_id:
            return qs.filter(enseignant_id=enseignant_id)

        return qs

    def perform_create(self, serializer):
        annee = AnneeScolaire.objects.filter(
            tenant=self.request.user.tenant,
            actif=True
        ).first()

        if not annee:
            raise ValidationError(
                {"detail": "Aucune année scolaire active."}
            )

        serializer.save(
            tenant=self.request.user.tenant,
            annee=annee
        )

    def create(self, request, *args, **kwargs):
        # 🔐 Seul l’admin tenant peut affecter
        if request.user.role != "ADMIN_TENANT":
            return Response(
                {"detail": "Action non autorisée."},
                status=403,
            )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if request.user.role != "ADMIN_TENANT":
            return Response(
                {"detail": "Action non autorisée."},
                status=403,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != "ADMIN_TENANT":
            return Response(
                {"detail": "Action non autorisée."},
                status=403,
            )
        return super().destroy(request, *args, **kwargs)


class MesClassesView(APIView):
    permission_classes = [IsAuthenticated, IsEnseignant]

    def get(self, request):
        classes = Classe.objects.filter(
            tenant=request.user.tenant,
            affectations_enseignants__enseignant=request.user,
        ).distinct()

        return Response(
            ClasseSerializer(classes, many=True).data
        )

class EnseignantDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "ENSEIGNANT":
            return Response({"detail": "Accès refusé"}, status=403)

        annee = AnneeScolaire.objects.filter(
            actif=True, tenant=user.tenant
        ).first()

        if not annee:
            return Response({"classes": []})

        affectations = (
            AffectationEnseignant.objects
            .filter(
                enseignant=user,
                annee=annee,
                tenant=user.tenant
            )
            .select_related("classe", "matiere")
        )

        classes_map = {}

        for aff in affectations:
            cid = aff.classe.id
            if cid not in classes_map:
                classes_map[cid] = {
                    "id": aff.classe.id,
                    "nom": aff.classe.libelle,
                    "niveau": aff.classe.niveau,
                    "matieres": [],
                }

            classes_map[cid]["matieres"].append(aff.matiere.nom_matiere)

        serializer = ClasseDashboardSerializer(
            classes_map.values(), many=True
        )

        return Response({
            "enseignant": user.get_full_name(),
            "classes": serializer.data
        })


class ElevesClasseEnseignantView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, classe_id):
        user = request.user

        if user.role != "ENSEIGNANT":
            return Response(
                {"detail": "Accès refusé"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not est_enseignant_affecte_a_classe(
            enseignant=user,
            classe_id=classe_id,
            tenant=user.tenant,
        ):
            return Response(
                {"detail": "Vous n’êtes pas affecté à cette classe pour l’année en cours"},
                status=status.HTTP_403_FORBIDDEN,
            )

        eleves = Eleve.objects.filter(
            classe_id=classe_id,
            tenant=user.tenant,
        ).order_by("nom", "prenom")

        data = [
            {
                "id": e.id,
                "nom_complet": f"{e.nom} {e.prenom}",
            }
            for e in eleves
        ]

        return Response(data, status=status.HTTP_200_OK)


