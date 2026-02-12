# config/evaluations/views.py

from evaluations.serializers import BulletinParentSerializer
from accounts.permissions import IsParent

from django.forms import ValidationError
from academics.serializers import ClasseSimpleSerializer, MatiereSimpleSerializer, ComposanteSerializer
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ModelViewSet, ViewSet

from django.http import FileResponse
from academics.models import AffectationClasse, Classe, Eleve, AffectationEnseignant, Matiere
from evaluations.services.pdf import generer_bulletin_pdf
from evaluations.models import Bulletin
from evaluations.services.bulletin_builder import build_bulletin_details

from .models import Bulletin, Note, Trimestre, Validation
from .serializers import BulletinDetailSerializer, BulletinReadSerializer, TrimestreSerializer, NoteSerializer
from .permissions import IsDirecteurOuAdminTenant, IsEnseignant, IsDirecteur
from .services.bulletins import generer_bulletin
from rest_framework.viewsets import ReadOnlyModelViewSet
from .models import AnneeScolaire, Bareme, Composante
from django.db import transaction
from django.utils import timezone

class BulletinViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Accès lecture + actions métier explicites sur les bulletins
    """
    serializer_class = BulletinReadSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Bulletin.objects.filter(tenant=user.tenant)

        if user.role == "PARENT":
            # À adapter plus tard : parent -> élèves
            return qs.none()

        return qs

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

        # 🔥 recalcul obligatoire avant validation
        bulletin = generer_bulletin(
            tenant=request.user.tenant,
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre
        )

        bulletin.refresh_from_db()

        if not bulletin.total_max or bulletin.total_max <= 0:
            return Response(
                {"detail": "Notes non complètes."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if bulletin.moyenne_sur_10 is None:
            return Response(
                {"detail": "Moyenne non calculée."},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        if bulletin.statut != "VALIDE_ENSEIGNANT":
            return Response(
                {"detail": "Bulletin non validé par l’enseignant."},
                status=status.HTTP_400_BAD_REQUEST
            )

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

class EnseignantTrimestreViewSet(ReadOnlyModelViewSet):
    serializer_class = TrimestreSerializer
    permission_classes = [IsEnseignant]

    def get_queryset(self):
        return Trimestre.objects.filter(
            tenant=self.request.user.tenant,
            annee__actif=True
        )


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
        generer_bulletin(
            tenant=request.user.tenant,
            eleve=eleve,
            trimestre=trimestre,
            lecture_seule=True
        )

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
        note_directe = None
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

                note_directe = {
                    "matiere_id": b.matiere.id,
                    "matiere_nom": b.matiere.nom,
                    "valeur": note.valeur if note else None,
                    "valeur_max": b.valeur_max,
                }

        return Response({
            "bulletin_id": bulletin.id,
            "statut": bulletin.statut,
            "notes": lignes,
            "note_directe": note_directe,
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

        # 🔐 Sécurité : uniquement pour les parents
        if user.role != "PARENT":
            return Bulletin.objects.none()

        # Parent lié à l'utilisateur
        parent = user.parent_profile  # OneToOne

        # Élèves associés au parent
        eleves = parent.eleves.all()

        # Bulletins des élèves du parent
        return Bulletin.objects.filter(
            eleve__in=eleves,
            statut="PUBLIE",  # important : le parent ne voit que les bulletins publiés
        ).select_related("eleve", "eleve__classe", "trimestre")

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        bulletin = self.get_object()

        path = generer_bulletin_pdf(bulletin=bulletin)

        return FileResponse(
            open(path, "rb"),
            content_type="application/pdf",
            filename=f"bulletin_{bulletin.id}.pdf",
        )
