# config/evaluations/views.py

from notifications.services import create_event
from rest_framework.decorators import api_view
from core.permissions import IsAdminTenantOrDirecteur
from core.views import TenantModelViewSet
from evaluations.serializers import BulletinParentSerializer
from accounts.permissions import IsParent
from django.db.models import Avg, Count, Case, When, IntegerField, Q
from rest_framework.permissions import IsAuthenticated
from evaluations.services.bulletins import generer_bulletin

from django.forms import ValidationError
from academics.serializers import ClasseSimpleSerializer, MatiereSimpleSerializer, ComposanteSerializer
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ModelViewSet, ViewSet

from django.http import FileResponse
from academics.models import AffectationClasse, Classe, Eleve, Matiere
from evaluations.services.pdf import generer_bulletin_pdf
from evaluations.services.bulletin_builder import build_bulletin_details
from django_filters.rest_framework import DjangoFilterBackend

from .models import Appreciation, Bulletin, Note, Trimestre, Validation, DecisionConseil
from .serializers import AppreciationSerializer, BulletinDetailSerializer, BulletinReadSerializer, TrimestreSerializer, NoteSerializer
from .permissions import IsDirecteurOuAdminTenant, IsEnseignant, IsDirecteur
from .services.bulletins import generer_bulletin
from rest_framework.viewsets import ReadOnlyModelViewSet
from .models import AnneeScolaire, Bareme, Composante
from django.db import transaction
from django.utils import timezone

class BulletinViewSet(TenantModelViewSet, ReadOnlyModelViewSet):
    queryset = Bulletin.objects.select_related(
        "eleve",
        "eleve__classe",
        "trimestre",
        "decision"
    )
    serializer_class = BulletinReadSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = ["statut", "trimestre"]

    search_fields = [
        "eleve__nom",
        "eleve__prenom",
        "eleve__matricule",
    ]

    ordering_fields = [
        "moyenne_sur_10",
        "rang",
        "statut",
        "date_generation",
    ]

    ordering = ["-date_generation"]

    # ======================================================
    # VALIDATION ENSEIGNANT
    # ======================================================
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsEnseignant],
        url_path="valider_enseignant"
    )
    @transaction.atomic
    def valider_enseignant(self, request, pk=None):
        bulletin = self.get_object()

        if bulletin.statut != "BROUILLON":
            return Response(
                {"detail": "Bulletin déjà validé ou publié."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 recalcul
        try:
            bulletin = generer_bulletin(
                tenant=request.user.tenant,
                eleve=bulletin.eleve,
                trimestre=bulletin.trimestre
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        bulletin.refresh_from_db()

        # 🔥 contrôles métier
        if bulletin.total_max <= 0:
            return Response(
                {"detail": "Barèmes non configurés ou incomplets."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if bulletin.moyenne_sur_10 is None:
            return Response(
                {"detail": "Moyenne non calculée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 validation
        bulletin.statut = "VALIDE_ENSEIGNANT"
        bulletin.save(update_fields=["statut"])

        Validation.objects.create(
            tenant=request.user.tenant,
            bulletin=bulletin,
            utilisateur=request.user,
            action="VALIDE_ENSEIGNANT"
        )

        return Response(
            BulletinReadSerializer(bulletin).data,
            status=status.HTTP_200_OK
        )

    # ======================================================
    # VALIDATION DIRECTEUR
    # ======================================================
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsDirecteurOuAdminTenant],
        url_path="valider_directeur"
    )
    @transaction.atomic
    def valider_directeur(self, request, pk=None):
        bulletin = self.get_object()
        user = request.user

        if bulletin.statut != "VALIDE_ENSEIGNANT":
            return Response(
                {"detail": "Bulletin non validé par l’enseignant."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 GESTION DÉCISION
        if bulletin.trimestre.numero == 3:
            data = request.data.get("decision")

            if not data:
                return Response(
                    {"detail": "Décision obligatoire pour le 3e trimestre."},
                    status=400
                )

            DecisionConseil.objects.update_or_create(
                bulletin=bulletin,
                defaults={
                    "tenant": bulletin.tenant,
                    "decision": data.get("decision"),
                    "mention": data.get("mention"),
                    "commentaire": data.get("commentaire"),
                    "autorise_examen": data.get("autorise_examen", False),
                    "cree_par": user,
                }
            )

        # 🔥 validation
        bulletin.statut = "VALIDE_DIRECTEUR"
        bulletin.save(update_fields=["statut"])

        Validation.objects.create(
            tenant=request.user.tenant,
            bulletin=bulletin,
            utilisateur=request.user,
            action="VALIDE_DIRECTEUR"
        )

        return Response(
            BulletinReadSerializer(bulletin).data,
            status=status.HTTP_200_OK
        )

    # ======================================================
    # PUBLICATION
    # ======================================================
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsDirecteurOuAdminTenant],
        url_path="publier"
    )
    @transaction.atomic
    def publier(self, request, pk=None):
        bulletin = self.get_object()

        if bulletin.trimestre.numero == 3 and not hasattr(bulletin, "decision"):
            return Response(
                {"detail": "Décision du conseil obligatoire."},
                status=400
            )

        if bulletin.statut != "VALIDE_DIRECTEUR":
            return Response(
                {"detail": "Bulletin non validé par le directeur."},
                status=status.HTTP_400_BAD_REQUEST
            )

        bulletin.statut = "PUBLIE"
        bulletin.date_generation = timezone.now()
        bulletin.save(update_fields=["statut", "date_generation"])

        Validation.objects.create(
            tenant=request.user.tenant,
            bulletin=bulletin,
            utilisateur=request.user,
            action="PUBLIE"
        )

        return Response(
            BulletinReadSerializer(bulletin).data,
            status=status.HTTP_200_OK
        )
    # ======================================================
    # EXPORT PDF
    # ======================================================
    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsDirecteurOuAdminTenant],
        url_path="pdf"
    )
    def export_pdf(self, request, pk=None):
        bulletin = self.get_object()

        if bulletin.statut != "PUBLIE":
            return Response(
                {"detail": "Bulletin non publié."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 RE-GÉNÉRATION MÉTIER (indispensable)
        bulletin = generer_bulletin(
            tenant=request.user.tenant,
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre,
            lecture_seule=True
        )

        filepath = generer_bulletin_pdf(bulletin=bulletin)

        return FileResponse(
            open(filepath, "rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"bulletin_{bulletin.eleve.id}_T{bulletin.trimestre.numero}.pdf"
        )

    # ======================================================
    # GÉNÉRATION EXPLICITE (ENSEIGNANT)
    # ======================================================
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsEnseignant],
        url_path="generer"
    )
    def generer(self, request):
        eleve_id = request.data.get("eleve")
        trimestre_id = request.data.get("trimestre")

        if not eleve_id or not trimestre_id:
            return Response(
                {"detail": "Élève et trimestre requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        eleve = get_object_or_404(
            Eleve,
            id=eleve_id,
            tenant=request.user.tenant
        )

        trimestre = get_object_or_404(
            Trimestre,
            id=trimestre_id,
            tenant=request.user.tenant
        )

        bulletin = generer_bulletin(
            tenant=request.user.tenant,
            eleve=eleve,
            trimestre=trimestre
        )

        return Response(
            BulletinReadSerializer(bulletin).data,
            status=status.HTTP_200_OK
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="stats",
        permission_classes=[IsDirecteurOuAdminTenant]
    )
    def stats(self, request):
        qs = self.get_queryset()

        total = qs.count()

        moyenne = qs.aggregate(
            avg=Avg("moyenne_sur_10")
        )["avg"] or 0

        publies = qs.filter(statut="PUBLIE").count()

        taux_reussite = qs.filter(
            moyenne_sur_10__gte=5
        ).count()

        return Response({
            "moyenne_generale": round(moyenne, 2),
            "taux_reussite": round((taux_reussite / total) * 100, 2) if total else 0,
            "bulletins_publies": publies,
            "effectif": total,
        })
    
    @action(
        detail=False,
        methods=["get"],
        url_path="stats-par-classe",
        permission_classes=[IsDirecteurOuAdminTenant]
    )
    def stats_par_classe(self, request):
        qs = self.get_queryset()

        data = (
            qs.values(
                "eleve__classe__id",
                "eleve__classe__nom"
            )
            .annotate(
                moyenne=Avg("moyenne_sur_10"),
                effectif=Count("id"),
                taux_reussite=Count(
                    Case(
                        When(moyenne_sur_10__gte=5, then=1),
                        output_field=IntegerField(),
                    )
                )
            )
        )

        result = []

        for d in data:
            total = d["effectif"] or 0
            reussite = d["taux_reussite"] or 0

            result.append({
                "classe_id": d["eleve__classe__id"],
                "classe": d["eleve__classe__nom"],
                "moyenne": round(d["moyenne"] or 0, 2),
                "effectif": total,
                "taux_reussite": round((reussite / total) * 100, 2) if total else 0,
            })

        return Response(result)
    
    @action(
        detail=False,
        methods=["get"],
        url_path="alertes",
        permission_classes=[IsDirecteurOuAdminTenant]
    )
    def alertes(self, request):
        qs = self.get_queryset()

        # 🔴 élèves en difficulté (< 5)
        en_difficulte = qs.filter(moyenne_sur_10__lt=5).count()

        # 🔴 bulletins non validés
        non_valides = qs.exclude(statut="PUBLIE").count()

        # 🔴 meilleurs élèves
        excellents = qs.filter(moyenne_sur_10__gte=8).count()

        return Response({
            "eleves_en_difficulte": en_difficulte,
            "bulletins_non_publies": non_valides,
            "eleves_excellents": excellents,
        })
    
    @action(
        detail=False,
        methods=["get"],
        url_path="evolution",
        permission_classes=[IsDirecteurOuAdminTenant]
    )
    def evolution(self, request):
        qs = self.get_queryset()

        data = (
            qs.values("trimestre__numero")
            .annotate(moyenne=Avg("moyenne_sur_10"))
            .order_by("trimestre__numero")
        )

        return Response([
            {
                "trimestre": d["trimestre__numero"],
                "moyenne": round(d["moyenne"] or 0, 2)
            }
            for d in data
        ])
    
    @action(
        detail=False,
        methods=["get"],
        url_path="top-eleves",
        permission_classes=[IsDirecteurOuAdminTenant]
    )
    def top_eleves(self, request):
        qs = self.get_queryset().select_related(
            "eleve__classe",
            "trimestre"
        )

        top = qs.order_by("-moyenne_sur_10")[:5]
        flop = qs.order_by("moyenne_sur_10")[:5]

        return Response({
            "top": [
                {
                    "nom": b.eleve.nom,
                    "prenom": b.eleve.prenom,
                    "classe": b.eleve.classe.nom if b.eleve.classe else None,
                    "trimestre": b.trimestre.numero,  # 🔥 AJOUT
                    "moyenne": b.moyenne_sur_10,
                } for b in top
            ],
            "flop": [
                {
                    "nom": b.eleve.nom,
                    "prenom": b.eleve.prenom,
                    "classe": b.eleve.classe.nom if b.eleve.classe else None,
                    "trimestre": b.trimestre.numero,  # 🔥 AJOUT
                    "moyenne": b.moyenne_sur_10,
                } for b in flop
            ]
        })

    @action(detail=False, methods=["post"], url_path="valider-masse")
    def valider_masse(self, request):
        ids = request.data.get("ids", [])

        bulletins = self.get_queryset().filter(id__in=ids)

        # 🔥 BLOQUER si T3
        if bulletins.filter(trimestre__numero=3).exists():
            return Response(
                {"detail": "Utilisez la validation avec conseil pour le 3e trimestre"},
                status=400
            )

        updated = bulletins.update(statut="VALIDE_DIRECTEUR")

        return Response({"updated": updated})
    
    @action(detail=False, methods=["post"], url_path="valider-masse-conseil")
    def valider_masse_conseil(self, request):
        ids = request.data.get("ids", [])
        decision_data = request.data.get("decision")

        if not decision_data:
            return Response(
                {"detail": "Décision obligatoire pour le 3e trimestre"},
                status=400
            )

        bulletins = self.get_queryset().filter(
            id__in=ids,
            trimestre__numero=3
        )

        updated = 0

        for bulletin in bulletins:

            DecisionConseil.objects.update_or_create(
                bulletin=bulletin,
                defaults={
                    "tenant": bulletin.tenant,
                    "decision": decision_data.get("decision"),
                    "mention": decision_data.get("mention"),
                    "commentaire": decision_data.get("commentaire"),
                    "cree_par": request.user,
                }
            )

            bulletin.statut = "VALIDE_DIRECTEUR"
            bulletin.save()

            updated += 1

        return Response({"updated": updated})

    # @action(detail=False, methods=["post"], url_path="valider-masse")
    # def valider_masse(self, request):
    #     ids = request.data.get("ids", [])

    #     bulletins = self.get_queryset().filter(id__in=ids)

    #     updated = 0

    #     for bulletin in bulletins:

    #         if bulletin.trimestre.numero == 3:
    #             decision_data = request.data.get("decision")

    #             if not decision_data:
    #                 return Response(
    #                     {"detail": "Décision obligatoire pour le 3e trimestre"},
    #                     status=400
    #                 )

    #             DecisionConseil.objects.update_or_create(
    #                 bulletin=bulletin,
    #                 defaults={
    #                     "tenant": bulletin.tenant,
    #                     "decision": decision_data.get("decision"),
    #                     "mention": decision_data.get("mention"),
    #                     "commentaire": decision_data.get("commentaire"),
    #                     "cree_par": request.user,
    #                 }
    #             )

    #         bulletin.statut = "VALIDE_DIRECTEUR"
    #         bulletin.save()

    #         updated += 1

    #     return Response({
    #         "updated": updated
    #     })


    @action(detail=False, methods=["post"], url_path="publier-masse")
    def publier_masse(self, request):
        ids = request.data.get("ids", [])

        bulletins = self.get_queryset().filter(id__in=ids)

        updated = bulletins.update(statut="PUBLIE")

        return Response({
            "updated": updated
        })
    
    @action(detail=True, methods=["post"])
    def definir_decision(self, request, pk=None):
        bulletin = self.get_object()
        user = request.user

        if user.role != "DIRECTEUR":
            return Response({"error": "Accès refusé"}, status=403)

        if bulletin.trimestre.numero != 3:
            return Response({"error": "Seulement 3e trimestre"}, status=400)

        if bulletin.statut != "VALIDE_DIRECTEUR":
            return Response({"error": "Bulletin non validé"}, status=400)

        data = request.data

        decision_obj, _ = DecisionConseil.objects.update_or_create(
            bulletin=bulletin,
            defaults={
                "tenant": bulletin.tenant,
                "decision": data.get("decision"),
                "mention": data.get("mention"),
                "commentaire": data.get("commentaire"),
                "autorise_examen": data.get("autorise_examen", False),
                "cree_par": user,
            }
        )

        return Response({"success": True})

class TrimestreViewSet(TenantModelViewSet):
    queryset = Trimestre.objects.all()
    serializer_class = TrimestreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        qs = Trimestre.objects.all()

        if not (user.is_superuser or getattr(user, "role", None) == "ADMIN_SAAS"):
            qs = qs.filter(tenant=user.tenant)

        return qs.filter(annee__actif=True).order_by("numero")

    def perform_create(self, serializer):
        user = self.request.user

        if user.is_superuser or getattr(user, "role", None) == "ADMIN_SAAS":
            tenant = serializer.validated_data.get("tenant")

            if not tenant:
                raise ValidationError("Tenant requis")

            serializer.save(tenant=tenant)
        else:
            serializer.save(tenant=user.tenant)

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        trimestre = self.get_object()

        if trimestre.cloture:
            return Response(
                {"error": "Impossible d’activer un trimestre clôturé"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # désactiver tous les autres trimestres de la même année
        Trimestre.objects.filter(
            tenant=trimestre.tenant,
            annee=trimestre.annee
        ).update(actif=False)

        trimestre.actif = True
        trimestre.save()

        return Response({"status": "trimestre activé"})
    
    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        trimestre = self.get_object()

        if trimestre.cloture:
            return Response(
                {"error": "Ce trimestre est déjà clôturé"},
                status=status.HTTP_400_BAD_REQUEST
            )

        trimestre.cloture = True
        trimestre.actif = False
        trimestre.save()

        return Response({"status": "trimestre clôturé"})


class EnseignantComposanteViewSet(ReadOnlyModelViewSet):
    serializer_class = ComposanteSerializer
    permission_classes = [IsEnseignant]

    def get_queryset(self):
        classe_id = self.request.query_params.get("classe")
        annee_active = AnneeScolaire.objects.filter(
            tenant=self.request.user.tenant,
            actif=True
        ).first()

        return Composante.objects.filter(
            bareme__classe_id=classe_id,
            bareme__annee=annee_active,
            tenant=self.request.user.tenant
        ).distinct()
    

class EnseignantNoteViewSet(ModelViewSet):
    serializer_class = NoteSerializer
    permission_classes = [IsEnseignant]

    def get_queryset(self):
        return Note.objects.filter(
            tenant=self.request.user.tenant,
            eleve__id=self.kwargs.get("eleve_id"),
            trimestre_id=self.request.query_params.get("trimestre")
        )

    from evaluations.models import Bulletin

    @action(
        detail=False,
        methods=["get"],
        url_path=r"eleves/(?P<eleve_id>\d+)/notes"
    )
    def notes_eleve(self, request, eleve_id=None):
        trimestre_id = request.query_params.get("trimestre")
        if not trimestre_id:
            return Response(
                {"detail": "Trimestre requis"},
                status=400
            )

        eleve = get_object_or_404(
            Eleve,
            id=eleve_id,
            tenant=request.user.tenant
        )

        trimestre = get_object_or_404(
            Trimestre,
            id=trimestre_id,
            tenant=request.user.tenant
        )

        # 🔹 bulletin implicite (créé si absent)
        bulletin, _ = Bulletin.objects.get_or_create(
            tenant=request.user.tenant,
            eleve=eleve,
            trimestre=trimestre,
            defaults={
                "statut": "BROUILLON",
                "total_points": 0,
                "total_max": 0,
                "moyenne_sur_10": 0,
            }
        )

        # recalcul SANS changer le statut
        # generer_bulletin(
        #     tenant=request.user.tenant,
        #     eleve=eleve,
        #     trimestre=trimestre,
        #     lecture_seule=True
        # )

        annee = eleve.classe.annee

        baremes = Bareme.objects.filter(
            classe=eleve.classe,
            annee=annee,
            tenant=request.user.tenant
        ).select_related("composante", "matiere")

        notes = Note.objects.filter(
            eleve=eleve,
            trimestre=trimestre,
            tenant=request.user.tenant
        )

        notes_map = {n.composante_id: n for n in notes}

        lignes = []
        notes_directes = []
        for b in baremes:

            # =========================
            # CAS PAR COMPOSANTE
            # =========================
            if b.composante_id:
                note = notes_map.get(b.composante_id)

                lignes.append({
                    "composante_id": b.composante.id,
                    "composante_nom": b.composante.nom,
                    "matiere_nom": b.composante.matiere.nom,
                    "type": b.composante.type,
                    "valeur": note.valeur if note else None,
                    "valeur_max": b.valeur_max,
                })

            # =========================
            # CAS MATIÈRE DIRECTE
            # =========================
            elif b.matiere_id:
                note = Note.objects.filter(
                    tenant=request.user.tenant,
                    eleve=eleve,
                    trimestre=trimestre,
                    matiere=b.matiere
                ).first()

                notes_directes.append({
                    "matiere_id": b.matiere.id,
                    "matiere_nom": b.matiere.nom,
                    "valeur": note.valeur if note else None,
                    "valeur_max": b.valeur_max,
                })

        return Response({
            "bulletin_id": bulletin.id,
            "statut": bulletin.statut,
            "notes": lignes,
            "note_directe": notes_directes,
        })

    def perform_create(self, serializer):
        data = serializer.validated_data

        note, created = Note.objects.update_or_create(
            tenant=self.request.user.tenant,
            eleve=data["eleve"],
            composante=data["composante"],
            trimestre=data["trimestre"],
            defaults={
                "valeur": data.get("valeur")
            }
        )

        serializer.instance = note

    @action(detail=False, methods=["post"])
    def save_note(self, request):
        """
        Sauvegarde d'une note enseignant.
        Supporte :
        - note PAR_COMPOSANTE
        - note DIRECTE (par matière)
        """

        eleve_id = request.data.get("eleve")
        trimestre_id = request.data.get("trimestre")
        composante_id = request.data.get("composante")
        matiere_id = request.data.get("matiere")
        valeur = request.data.get("valeur")

        # =========================
        # VALIDATIONS DE BASE
        # =========================
        if not eleve_id or not trimestre_id:
            return Response(
                {"detail": "Élève et trimestre requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if valeur is None:
            return Response(
                {"detail": "Valeur de note requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔒 EXACTEMENT UNE CIBLE
        if bool(composante_id) == bool(matiere_id):
            return Response(
                {
                    "detail": (
                        "Fournir soit 'composante', soit 'matiere', "
                        "mais pas les deux."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        eleve = get_object_or_404(
            Eleve,
            id=eleve_id,
            tenant=request.user.tenant,
        )
        trimestre = get_object_or_404(
            Trimestre,
            id=trimestre_id,
        )

        # =========================
        # CAS PAR COMPOSANTE
        # =========================
        if composante_id:
            composante = get_object_or_404(
                Composante,
                id=composante_id,
            )

            note, created = Note.objects.get_or_create(
                tenant=request.user.tenant,
                eleve=eleve,
                trimestre=trimestre,
                composante=composante,
                defaults={
                    "valeur": valeur,
                },
            )

            if not created:
                note.valeur = valeur

        # =========================
        # CAS DIRECT (MATIÈRE)
        # =========================
        else:
            matiere = get_object_or_404(
                Matiere,
                id=matiere_id,
            )

            note, created = Note.objects.get_or_create(
                tenant=request.user.tenant,
                eleve=eleve,
                trimestre=trimestre,
                matiere=matiere,
                defaults={
                    "valeur": valeur,
                },
            )

            if not created:
                note.valeur = valeur

        # =========================
        # VALIDATION MÉTIER (clean)
        # =========================
        try:
            note.full_clean()
            note.save()

            # 🔥 DÉCLENCHEMENT ÉVÉNEMENT (SEULEMENT SI CRÉATION)
            if created:
                create_event(
                    type="NOTE_AJOUTEE",
                    reference_id=note.eleve_id,
                    reference_type="NOTE",
                    tenant_id=note.tenant_id  # OK même si on ne s’en sert plus vraiment
                )
                
        except ValidationError as e:
            return Response(
                {"detail": e.message_dict or e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NoteSerializer(note)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

class EnseignantBulletinViewSet(ViewSet):
    """
    Lecture seule des bulletins publiés
    """

    def list(self, request):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"(?P<eleve_id>\d+)"
    )
    def bulletin_eleve(self, request, eleve_id=None):
        trimestre_id = request.query_params.get("trimestre")

        bulletin = Bulletin.objects.filter(
            eleve_id=eleve_id,
            trimestre_id=trimestre_id,
            statut="PUBLIE"
        ).select_related(
            "eleve__classe"
        ).first()

        if not bulletin:
            return Response(
                {"detail": "Bulletin non publié ou inexistant."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 🔐 CONTRÔLE D’ACCÈS ENSEIGNANT (CORRECT)
        if request.user.role == "ENSEIGNANT":
            classes_ids = AffectationClasse.objects.filter(
                enseignant=request.user
            ).values_list("classe_id", flat=True)

            if bulletin.eleve.classe_id not in classes_ids:
                return Response(
                    {"detail": "Accès interdit à ce bulletin."},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = BulletinDetailSerializer(bulletin)
        return Response(serializer.data)
    
    
@action(detail=False, methods=["get"])
def classes(self, request):
    """
    Classes auxquelles l’enseignant est affecté
    """
    if request.user.role != "ENSEIGNANT":
        return Response(status=status.HTTP_403_FORBIDDEN)

    classes = Classe.objects.filter(
        affectationenseignant__enseignant=request.user,
        affectationenseignant__tenant=request.tenant,
    ).distinct()

    serializer = ClasseSimpleSerializer(classes, many=True)
    return Response(serializer.data)


@action(detail=False, methods=["get"])
def matieres(self, request):
    """
    Matières enseignées par l’enseignant dans une classe donnée
    """
    if request.user.role != "ENSEIGNANT":
        return Response(status=status.HTTP_403_FORBIDDEN)

    classe_id = request.query_params.get("classe")
    if not classe_id:
        return Response(
            {"detail": "classe manquante"},
            status=status.HTTP_400_BAD_REQUEST
        )

    matieres = Matiere.objects.filter(
        affectationenseignant__enseignant=request.user,
        affectationenseignant__classe_id=classe_id,
        affectationenseignant__tenant=request.tenant,
    ).distinct()

    serializer = MatiereSimpleSerializer(matieres, many=True)
    return Response(serializer.data)


class ParentBulletinViewSet(ReadOnlyModelViewSet):
    serializer_class = BulletinParentSerializer
    permission_classes = [IsParent]

    def get_queryset(self):
        user = self.request.user

        if user.role != "PARENT":
            return Bulletin.objects.none()

        parent = user.parent_profile

        # 🔒 sécurité : vérifier tenant
        tenant = user.tenant

        eleves = parent.eleves.filter(tenant=tenant)
        print("ELEVE IDS:", eleves.values_list("id", flat=True))
        return Bulletin.objects.filter(
            eleve__in=eleves,
            eleve__tenant=tenant,
            tenant=tenant,
            statut="PUBLIE",
        ).select_related(
            "eleve",
            "eleve__classe",
            "trimestre"
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        bulletin = self.get_object()

        # 🔥 RECONSTRUIRE LE BULLETIN PROPREMENT (même logique que directeur)
        bulletin = generer_bulletin(
            tenant=bulletin.tenant,
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre,
            lecture_seule=True  # 🔥 IMPORTANT
        )

        path = generer_bulletin_pdf(bulletin=bulletin)

        if bulletin.statut != "PUBLIE":
            return Response({"error": "Bulletin non disponible"}, status=403)

        return FileResponse(
            open(path, "rb"),
            content_type="application/pdf",
            filename=f"bulletin_{bulletin.id}.pdf",
        )

@api_view(["GET"])
def verify_bulletin(request, token):
    try:
        bulletin = Bulletin.objects.select_related(
            "eleve", "tenant", "trimestre"
        ).get(verification_token=token)

        return Response({
            "valide": True,
            "eleve": f"{bulletin.eleve.prenom} {bulletin.eleve.nom}",
            "classe": str(bulletin.eleve.classe),
            "ecole": bulletin.tenant.nom,
            "moyenne": bulletin.moyenne_sur_10,
            "rang": bulletin.rang,
            "statut": bulletin.statut,
        })

    except Bulletin.DoesNotExist:
        return Response({"valide": False}, status=404)
    

class AppreciationViewSet(TenantModelViewSet):
    queryset = Appreciation.objects.all()
    serializer_class = AppreciationSerializer
    permission_classes = [IsAuthenticated, IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Appreciation.objects.filter(
            tenant=self.request.user.tenant
        )

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )