# evaluations/services/bulletins.py

from django.db import transaction
from django.forms import ValidationError
import uuid

from academics.models import Matiere, Bareme
from evaluations.models import Note, Bulletin
from evaluations.services.classements import recalculer_rangs
from evaluations.services.appreciations import get_appreciation


@transaction.atomic
def generer_bulletin(*, tenant, eleve, trimestre, lecture_seule=False):
    """
    Génère ou régénère un bulletin trimestriel complet
    (calculs + structure matières / composantes pour le PDF)
    """

    # 🔒 Sécurité : interdiction modification si publié
    bulletin = Bulletin.objects.filter(
        tenant=tenant,
        eleve=eleve,
        trimestre=trimestre
    ).first()

    if bulletin and bulletin.statut == "PUBLIE" and not lecture_seule:
        raise ValidationError("Bulletin déjà publié : modification interdite.")

    classe = eleve.classe
    annee = classe.annee

    # =========================
    # RÉCUP DONNÉES
    # =========================
    notes = Note.objects.filter(
        tenant=tenant,
        eleve=eleve,
        trimestre=trimestre
    ).select_related("composante__matiere", "matiere")

    baremes = Bareme.objects.filter(
        tenant=tenant,
        classe=classe,
        annee=annee
    )

    # =========================
    # MAPS
    # =========================
    bareme_map_composante = {
        b.composante_id: b.valeur_max
        for b in baremes if b.composante_id
    }

    bareme_map_matiere = {
        b.matiere_id: b.valeur_max
        for b in baremes if b.matiere_id
    }

    notes_map_composante = {
        n.composante_id: n
        for n in notes if n.composante_id
    }

    notes_map_matiere = {
        n.matiere_id: n
        for n in notes if n.matiere_id
    }

    # =========================
    # CALCUL
    # =========================
    total_points = 0.0
    total_max = 0.0
    details = []

    matieres = Matiere.objects.filter(
        tenant=tenant,
        actif=True
    ).order_by("ordre_affichage")

    for matiere in matieres:

        # =========================
        # CAS DIRECT
        # =========================
        if matiere.type_evaluation == "DIRECTE":
            note = notes_map_matiere.get(matiere.id)
            bareme_val = bareme_map_matiere.get(matiere.id)

            if not bareme_val:
                raise ValidationError(
                    f"Barème manquant pour matière {matiere.nom}"
                )

            if note:
                details.append({
                    "matiere": matiere.nom,
                    "total_obtenu": note.valeur,
                    "total_max": bareme_val,
                    "composantes": [],
                })

                total_points += note.valeur
                total_max += bareme_val

            continue

        # =========================
        # CAS PAR COMPOSANTE
        # =========================
        composantes = matiere.composante_set.filter(
            tenant=tenant,
            actif=True
        )

        composantes_data = []
        total_matiere = 0.0
        total_matiere_max = 0.0

        for composante in composantes:
            note = notes_map_composante.get(composante.id)
            bareme_val = bareme_map_composante.get(composante.id)

            if not bareme_val:
                raise ValidationError(
                    f"Barème manquant pour {composante.nom}"
                )

            if not note:
                continue

            composantes_data.append({
                "nom": composante.nom,
                "obtenu": note.valeur,
                "max": bareme_val,
            })

            total_points += note.valeur
            total_max += bareme_val
            total_matiere += note.valeur
            total_matiere_max += bareme_val

        if composantes_data:
            details.append({
                "matiere": matiere.nom,
                "total_obtenu": total_matiere,
                "total_max": total_matiere_max,
                "composantes": composantes_data,
            })

    # =========================
    # MOYENNE
    # =========================
    moyenne_sur_10 = (
        round((total_points / total_max) * 10, 2)
        if total_max > 0 else None
    )

    appreciation = get_appreciation(
        tenant=tenant,
        moyenne=moyenne_sur_10
    )

    # =========================
    # SAUVEGARDE
    # =========================
    if bulletin:
        bulletin.total_points = total_points
        bulletin.total_max = total_max
        bulletin.moyenne_sur_10 = moyenne_sur_10
        bulletin.appreciation = appreciation
        bulletin.save()
    else:
        bulletin = Bulletin.objects.create(
            tenant=tenant,
            eleve=eleve,
            trimestre=trimestre,
            total_points=total_points,
            total_max=total_max,
            moyenne_sur_10=moyenne_sur_10,
            appreciation=appreciation,
            statut="BROUILLON"
        )

    # =========================
    # DETAILS POUR PDF
    # =========================
    bulletin.details_matiere = details

    # =========================
    # CLASSEMENT
    # =========================
    recalculer_rangs(
        tenant=tenant,
        classe=classe,
        trimestre=trimestre
    )

    # =========================
    # TOKEN QR (AJOUT)
    # =========================
    if not bulletin.verification_token:
        bulletin.verification_token = uuid.uuid4().hex
        bulletin.save()

    return bulletin