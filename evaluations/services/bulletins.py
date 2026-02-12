# evaluations/services/bulletins/py

from django.db import transaction
from django.forms import ValidationError
from academics.models import Matiere, Bareme
from evaluations.models import Note, Bulletin, Appreciation
from evaluations.services.classements import recalculer_rangs


from django.db import transaction
from django.forms import ValidationError

from academics.models import Matiere, Bareme
from evaluations.models import Note, Bulletin, Appreciation
from evaluations.services.classements import recalculer_rangs


@transaction.atomic
def generer_bulletin(*, tenant, eleve, trimestre, lecture_seule=False):
    """
    Génère ou régénère un bulletin trimestriel complet
    (calculs + structure matières / composantes pour le PDF)
    """

    # 🔒 Sécurité : interdiction de modification si déjà publié
    bulletin = Bulletin.objects.filter(
        tenant=tenant,
        eleve=eleve,
        trimestre=trimestre
    ).first()

    if bulletin and bulletin.statut == "PUBLIE" and not lecture_seule:
        raise ValidationError("Bulletin déjà publié : modification interdite.")

    classe = eleve.classe
    annee = classe.annee

    total_points = 0.0
    total_max = 0.0
    details = []

    # Parcours structuré : Matière → (Composantes)
    matieres = Matiere.objects.filter(
        tenant=tenant,
        actif=True
    ).order_by("ordre_affichage")

    for matiere in matieres:
        composantes_data = []
        total_matiere = 0.0
        total_matiere_max = 0.0

        # =========================
        # CAS MATIÈRE DIRECTE
        # =========================
        if matiere.type_evaluation == "DIRECTE":
            # 🔑 récupérer la composante technique ("Note globale")
            composante = matiere.composante_set.filter(
                tenant=tenant
            ).first()

            if not composante:
                # aucune note possible si la composante n'existe pas
                continue

            note = Note.objects.filter(
                tenant=tenant,
                eleve=eleve,
                composante=composante,
                trimestre=trimestre
            ).first()

            if not note:
                continue

            try:
                bareme = Bareme.objects.get(
                    tenant=tenant,
                    composante=composante,
                    classe=classe,
                    annee=annee
                )
            except Bareme.DoesNotExist:
                raise ValidationError(
                    f"Barème manquant pour la matière {matiere.nom}."
                )

            details.append({
                "matiere": matiere.nom,
                "total_obtenu": note.valeur,
                "total_max": bareme.valeur_max,
                "composantes": [],  # matière directe → pas de sous-lignes
            })

            total_points += note.valeur
            total_max += bareme.valeur_max
            continue

        # ============================
        # CAS MATIÈRE AVEC COMPOSANTES
        # ============================
        composantes = matiere.composante_set.filter(
            tenant=tenant
        )

        for composante in composantes:
            note = Note.objects.filter(
                tenant=tenant,
                eleve=eleve,
                composante=composante,
                trimestre=trimestre
            ).first()

            if not note:
                continue

            try:
                bareme = Bareme.objects.get(
                    tenant=tenant,
                    composante=composante,
                    classe=classe,
                    annee=annee
                )
            except Bareme.DoesNotExist:
                raise ValidationError(
                    f"Barème manquant pour {composante.nom}."
                )

            composantes_data.append({
                "nom": composante.nom,
                "obtenu": note.valeur,
                "max": bareme.valeur_max,
            })

            total_points += note.valeur
            total_max += bareme.valeur_max
            total_matiere += note.valeur
            total_matiere_max += bareme.valeur_max

        # On n’ajoute la matière que si elle a au moins une composante notée
        if composantes_data:
            details.append({
                "matiere": matiere.nom,
                "total_obtenu": total_matiere,
                "total_max": total_matiere_max,
                "composantes": composantes_data,
            })

    moyenne_sur_10 = (
        round((total_points / total_max) * 10, 2)
        if total_max > 0 else None
    )

    appreciation = None
    if moyenne_sur_10 is not None:
        appreciation = Appreciation.objects.filter(
            tenant=tenant,
            moyenne_min__lte=moyenne_sur_10,
            moyenne_max__gte=moyenne_sur_10
        ).first()

    bulletin, _ = Bulletin.objects.update_or_create(
        tenant=tenant,
        eleve=eleve,
        trimestre=trimestre,
        defaults={
            "total_points": total_points,
            "total_max": total_max,
            "moyenne_sur_10": moyenne_sur_10,
            "appreciation": appreciation,
            "statut": bulletin.statut if bulletin else "BROUILLON",
        }
    )

    # 📌 Attachement dynamique pour le PDF
    bulletin.details_matiere = details

    # Recalcul du classement
    recalculer_rangs(
        tenant=tenant,
        classe=classe,
        trimestre=trimestre
    )

    return bulletin

