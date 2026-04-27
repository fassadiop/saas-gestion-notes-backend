# academics/views.py

import mimetypes
from django.http import FileResponse, Http404
from django.utils import timezone

from django.http import FileResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.viewsets import ModelViewSet

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework.response import Response
from accounts import models
from accounts.permissions import IsAdminTenant, IsEnseignant
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from core.models import Message
from core.permissions import IsAdminTenantOrDirecteur
from core.views import TenantModelViewSet
from evaluations.models import Note
from .models import AffectationClasse, AnneeScolaire, DocumentEleve, Eleve, Classe, Inscription, Matiere, AffectationEnseignant, Bareme, Composante
from .serializers import AffectationClasseSerializer, AnneeScolaireSerializer, DocumentEleveSerializer, EleveSerializer, ClasseSerializer, ComposanteSerializer, ClasseDashboardSerializer, InscriptionCreateSerializer, InscriptionDetailSerializer, InscriptionListSerializer
from accounts.models import User
from academics.serializers import MatiereSerializer, BaremeSerializer
from .services.affectations import est_enseignant_affecte_a_classe
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied

from django.db.models import Avg, Count, Q, F, FloatField, ExpressionWrapper, OuterRef, Subquery


class ClasseViewSet(TenantModelViewSet):
    queryset = Classe.objects.select_related("annee")
    serializer_class = ClasseSerializer
    permission_classes = [IsAuthenticated, IsAdminTenantOrDirecteur]

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


class EleveViewSet(TenantModelViewSet):
    serializer_class = EleveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        qs = Eleve.objects.filter(
            tenant=user.tenant,
            actif=True  # 🔥 si soft delete
        )

        # 🔥 retrieve → accès direct
        if self.action == "retrieve":
            return qs

        classe_id = self.request.query_params.get("classe")

        # =========================
        # CAS ENSEIGNANT
        # =========================
        if user.role == "ENSEIGNANT":
            if not classe_id:
                return Eleve.objects.none()

            if not est_enseignant_affecte_a_classe(
                enseignant=user,
                classe_id=classe_id,
                tenant=user.tenant,
            ):
                return Eleve.objects.none()

            return qs.filter(
                inscriptions__classe_id=classe_id,
                inscriptions__actif=True
            ).distinct()

        # =========================
        # AUTRES ROLES
        # =========================
        if classe_id:
            return qs.filter(
                inscriptions__classe_id=classe_id,
                inscriptions__actif=True
            ).distinct()

        return qs
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        user = request.user

        # 🔐 sécurité enseignant
        if user.role == "ENSEIGNANT":
            if not est_enseignant_affecte_a_classe(
                enseignant=user,
                classe_id=instance.classe_id,
                tenant=user.tenant,
            ):
                return Response(status=403)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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

class AnneeScolaireViewSet(TenantModelViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        annee = self.get_object()

        # 🔥 transaction = cohérence
        with transaction.atomic():
            AnneeScolaire.objects.filter(
                tenant=request.user.tenant
            ).update(actif=False)

            annee.actif = True
            annee.save(update_fields=["actif"])

        return Response({"status": "annee activee"})

    @action(detail=True, methods=["post"])
    def desactiver(self, request, pk=None):
        annee = self.get_object()
        annee.actif = False
        annee.save(update_fields=["actif"])

        return Response(
            {"status": "annee desactivee"},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"])
    def active(self, request):
        annee = AnneeScolaire.objects.filter(
            tenant=request.user.tenant,
            actif=True
        ).first()

        if not annee:
            return Response(
                {"detail": "Aucune année active"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(annee)
        return Response(serializer.data)



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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(tenant=request.user.tenant)

        # 🔥 on sérialise UNE VRAIE INSTANCE
        output_serializer = self.get_serializer(instance)

        return Response(output_serializer.data, status=status.HTTP_201_CREATED)



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

        # -------------------------
        # 1. AFFECTATIONS
        # -------------------------
        affectations = (
            AffectationClasse.objects
            .filter(
                enseignant=user,
                annee=annee,
                tenant=user.tenant
            )
            .select_related("classe")
        )
        
        classes_ids = affectations.values_list("classe_id", flat=True).distinct()

        classes_map = {}

        for aff in affectations:
            cid = aff.classe.id
            if cid not in classes_map:
                classes_map[cid] = {
                    "id": aff.classe.id,
                    "nom": aff.classe.nom,
                    "niveau": aff.classe.niveau,
                    "matieres": [],
                }

            classes_map[cid]["matieres"].append("Non défini")

        # -------------------------
        # 2. ÉLÈVES
        # -------------------------
        eleves = Eleve.objects.filter(
            inscriptions__classe_id__in=classes_ids,
            inscriptions__actif=True,
            tenant=user.tenant
        ).distinct()

        total_eleves = eleves.count()

        # Répartition F/G
        repartition = {
            "garcons": eleves.filter(sexe="M").count(),
            "filles": eleves.filter(sexe="F").count(),
        }

        # -------------------------
        # 3. NOTES & MOYENNES
        # -------------------------
        notes = Note.objects.filter(
            eleve__inscriptions__classe_id__in=classes_ids,
            eleve__inscriptions__actif=True,
            tenant=user.tenant
        )

        bareme_subquery = Bareme.objects.filter(
            composante=OuterRef("composante"),
            classe__in=classes_ids,
            annee=annee,
            tenant=user.tenant
        ).values("valeur_max")[:1]

        notes_normalisees = notes.annotate(
            valeur_max=Subquery(bareme_subquery),
        ).filter(valeur_max__gt=0).annotate(
            note_sur_10=ExpressionWrapper(
                (F("valeur") * 10.0) / F("valeur_max"),
                output_field=FloatField()
            )
        )

        moyenne_classe = notes_normalisees.aggregate(
            moy=Avg("note_sur_10")
        )["moy"] or 0

        eleves_moyennes = (
            notes_normalisees
            .values("eleve_id", "eleve__nom", "eleve__prenom")
            .annotate(moyenne=Avg("note_sur_10"))
            .filter(moyenne__isnull=False)
        )

        # Top 5
        eleves_moyennes = eleves_moyennes.filter(moyenne__isnull=False)
        top5 = eleves_moyennes.order_by("-moyenne")[:5]

        # -------------------------
        # ANALYSE PÉDAGOGIQUE
        # -------------------------

        seuil_critique = 5
        seuil_risque = 6

        # 🔴 Élèves en difficulté
        en_difficulte = eleves_moyennes.filter(
            moyenne__lt=seuil_critique
        ).order_by("moyenne")[:5]

        # 🟠 À surveiller
        a_surveiller = eleves_moyennes.filter(
            moyenne__gte=seuil_critique,
            moyenne__lt=seuil_risque
        ).order_by("moyenne")[:5]

        # ⚫ Sans notes
        eleves_avec_notes_ids = eleves_moyennes.values_list("eleve_id", flat=True)

        sans_notes = eleves.exclude(id__in=eleves_avec_notes_ids)

        sans_notes_list = list(
            sans_notes.values(
                "id",
                "nom",
                "prenom"
            )
        )

        # -------------------------
        # TAUX DE RÉUSSITE (FIX)
        # -------------------------

        total = eleves_moyennes.count() or 1

        reussite = eleves_moyennes.filter(
            moyenne__gte=seuil_critique
        ).count()

        taux_reussite = (reussite / total) * 100

        # -------------------------
        # 4. ÉVOLUTION MOYENNE
        # -------------------------
        evolution = list(
            notes_normalisees
            .values("trimestre__numero")
            .annotate(moyenne=Avg("note_sur_10"))
            .order_by("trimestre__numero")
        )

        # -------------------------
        # 5. MESSAGES
        # -------------------------
        messages = Message.objects.filter(
            Q(type="DIRECTION") |
            Q(classe_id__in=classes_ids),
            tenant=user.tenant
        ).order_by("-created_at")[:5]

        # -------------------------
        # 6. SERIALIZATION SIMPLE
        # -------------------------
        serializer = ClasseDashboardSerializer(
            classes_map.values(), many=True
        )

        return Response({
            "enseignant": f"{user.first_name} {user.last_name}",
            "classes": serializer.data,

            "total_eleves": total_eleves,
            "moyenne_classe": round(moyenne_classe, 2),
            "taux_reussite": round(taux_reussite, 1),

            "repartition": repartition,  # ✔️ FIX

            "top5": list(
                top5.values(
                    "eleve_id",
                    "eleve__nom",
                    "eleve__prenom",
                    "moyenne"
                )
            ),
            "en_difficulte": list(
                en_difficulte.values(
                    "eleve_id",
                    "eleve__nom",
                    "eleve__prenom",
                    "moyenne"
                )
            ),

            "a_surveiller": list(
                a_surveiller.values(
                    "eleve_id",
                    "eleve__nom",
                    "eleve__prenom",
                    "moyenne"
                )
            ),

            "sans_notes": sans_notes_list,

            "evolution": list(evolution),
            "messages": list(messages.values("id", "titre", "contenu", "type")),
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


class InscriptionViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter
    ]
    filterset_fields = ["classe", "annee", "actif"]
    search_fields = ["eleve__nom", "eleve__prenom"]
    ordering_fields = ["date_inscription"]

    def get_queryset(self):
        user = self.request.user

        return Inscription.objects.filter(
            tenant=user.tenant
        ).select_related(
            "eleve",
            "classe",
            "annee"
        ).prefetch_related(
            "eleve__parents",
            "eleve__parents__user",
        ).order_by("-date_inscription", "-id")

    def get_serializer_class(self):
        if self.action == "create":
            return InscriptionCreateSerializer

        if self.action == "retrieve":
            return InscriptionDetailSerializer

        return InscriptionListSerializer

    def perform_create(self, serializer):
        # 🔒 contrôle rôle
        if self.request.user.role not in ["ADMIN_TENANT", "DIRECTEUR"]:
            raise PermissionDenied("Action non autorisée")

        serializer.save(tenant=self.request.user.tenant)

    def perform_destroy(self, instance):
        # 🔒 éviter suppression brute (historique important)
        raise PermissionDenied("Suppression interdite. Désactivez l'inscription.")

    def perform_update(self, serializer):
        instance = self.get_object()

        # Autoriser uniquement la désactivation
        if "actif" in serializer.validated_data:
            serializer.save()
        else:
            raise PermissionDenied("Modification interdite")
        
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        response.data["message"] = "Inscription réussie"

        return response
    

class DocumentEleveViewSet(ModelViewSet):
    queryset = DocumentEleve.objects.all()
    serializer_class = DocumentEleveSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user

        if user.role == "PARENT":
            return DocumentEleve.objects.filter(parent=user.parent_profile)

        elif user.role == "DIRECTEUR":
            return DocumentEleve.objects.filter(tenant=user.tenant)

        return DocumentEleve.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        eleve = serializer.validated_data["eleve"]
        file_obj = self.request.FILES.get("fichier")

        # 🔒 Vérification métier (critique)
        if user.role == "PARENT":
            if not hasattr(user, "parent_profile"):
                raise PermissionDenied("Profil parent introuvable")

            parent = user.parent_profile

            if not parent.eleves.filter(id=eleve.id).exists():
                raise PermissionDenied("Cet élève ne vous appartient pas")

        else:
            raise PermissionDenied("Seuls les parents peuvent uploader")

        serializer.save(
            parent=user.parent_profile,
            tenant=user.tenant,
            nom_original=file_obj.name if file_obj else "",
        )

    def get_content_type(self, obj):
        try:
            return obj.fichier.file.content_type
        except:
            type_guess, _ = mimetypes.guess_type(obj.fichier.name)
            return type_guess

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        user = request.user

        # 🔒 RBAC (inchangé)
        if user.role == "PARENT":
            if document.parent != user.parent_profile:
                raise PermissionDenied("Accès refusé")
        elif user.role == "DIRECTEUR":
            if document.tenant != user.tenant:
                raise PermissionDenied("Accès refusé")
        else:
            raise PermissionDenied("Accès refusé")

        if not document.fichier:
            raise Http404("Fichier introuvable")

        preview = request.query_params.get("preview", "false")

        # ✅ Détection fiable du type MIME
        content_type, _ = mimetypes.guess_type(document.fichier.name)

        return FileResponse(
            document.fichier.open("rb"),
            as_attachment=(preview != "true"),
            filename=document.nom_original or document.fichier.name,
            content_type=content_type or "application/octet-stream",
        )
    
    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        document = self.get_object()
        user = request.user

        if user.role != "DIRECTEUR":
            raise PermissionDenied("Seul le directeur peut valider")

        if document.tenant != user.tenant:
            raise PermissionDenied("Accès refusé")

        document.statut = "VALIDE"
        document.valide_par = user
        document.date_validation = timezone.now()
        document.save()

        return Response({"status": "document validé"})
    
    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        document = self.get_object()
        user = request.user

        if user.role != "DIRECTEUR":
            raise PermissionDenied("Seul le directeur peut rejeter")

        if document.tenant != user.tenant:
            raise PermissionDenied("Accès refusé")

        document.statut = "REJETE"
        document.valide_par = user
        document.date_validation = timezone.now()
        document.save()

        return Response({"status": "document rejeté"})
    

