# config/evaluations/services/generer_bulletin_pdf.py

import os
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
from django.db.models import Sum
from academics.models import Matiere
from evaluations.models import Note

def generer_bulletin_pdf(*, bulletin):
    """
    Génère le PDF officiel d'un bulletin trimestriel publié.
    Hypothèse : bulletin.statut == 'PUBLIE'
    """
    eleve = bulletin.eleve
    classe = eleve.classe
    annee = classe.annee

    # IMPORTANT :
    # On ne recalcule RIEN ici. On exploite uniquement les données déjà calculées.
    # Les lignes par matière doivent être préparées par generer_bulletin()
    # et accessibles via un helper ou un attribut sérialisable.
    # Hypothèse simple et robuste : bulletin.details_matiere (liste de dicts)
    # Si tu as un autre nom, adapte ici UNIQUEMENT.
    notes = (
        Note.objects
        .filter(
            tenant=bulletin.tenant,
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre
        )
        .select_related("composante__matiere")
    )
    
    lignes_map = {}

    for note in notes:
        matiere = note.composante.matiere.nom_matiere
        lignes_map.setdefault(matiere, {"matiere": matiere, "points_obtenus": 0, "points_max": 0})
        lignes_map[matiere]["points_obtenus"] += note.valeur

        # barème max (déjà défini en base, pas recalculé)
        lignes_map[matiere]["points_max"] += note.composante.bareme_set.get(
            classe=bulletin.eleve.classe,
            annee=bulletin.trimestre.annee,
            tenant=bulletin.tenant
        ).valeur_max

    lignes = list(lignes_map.values())
    context = {
        "ief": getattr(settings, "IEF_NAME", ""),
        "ecole": bulletin.tenant.nom,
        "annee_scolaire": f"{annee.date_debut.year} / {annee.date_fin.year}",
        "trimestre_label": bulletin.trimestre.get_numero_display(),
        "eleve": eleve,
        "classe": classe.libelle,
        "effectif": classe.effectif,
        "lignes": lignes,
        "total_points": bulletin.total_points,
        "total_max": bulletin.total_max,
        "moyenne_sur_10": bulletin.moyenne_sur_10,
        "rang": f"{bulletin.rang}e" if bulletin.rang else "—",
        "appreciation": bulletin.appreciation.libelle if bulletin.appreciation else "—",
        "observation": bulletin.observation,
    }

    html = render_to_string(
        "bulletins/bulletin_trimestriel.html",
        context
    )

    out_dir = os.path.join(settings.MEDIA_ROOT, "bulletins")
    os.makedirs(out_dir, exist_ok=True)

    filename = f"bulletin_{eleve.id}_T{bulletin.trimestre.numero}.pdf"
    filepath = os.path.join(out_dir, filename)

    HTML(string=html, base_url=settings.BASE_DIR).write_pdf(filepath)
    return filepath
