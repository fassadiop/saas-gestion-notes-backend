# evaluations/services/pdf.py

import os
import base64
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
from evaluations.models import Note

def image_base64(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generer_bulletin_pdf(*, bulletin):
    eleve = bulletin.eleve
    classe = eleve.classe
    annee = classe.annee

    lignes = getattr(bulletin, "details_matiere", [])

    context = {
        # 🔥 IMAGES BASE64
        "drapeau_sn_base64": image_base64(
            os.path.join(settings.BASE_DIR, "static", "images", "drapeau_sn.png")
        ),
        "logo_men_base64": image_base64(
            os.path.join(settings.BASE_DIR, "static", "images", "logo-men.png")
        ),

        # 🔥 DONNÉES BULLETIN
        "ecole": bulletin.tenant.nom,
        "annee_scolaire": f"{annee.date_debut.year} / {annee.date_fin.year}",
        "trimestre_label": bulletin.trimestre.get_numero_display(),
        "eleve": eleve,
        "classe": str(classe),
        "effectif": classe.effectif_prevu,
        "lignes": lignes,
        "total_points": bulletin.total_points,
        "total_max": bulletin.total_max,
        "moyenne_sur_10": bulletin.moyenne_sur_10,
        "rang": f"{bulletin.rang}e" if bulletin.rang else "—",
        "appreciation": bulletin.appreciation.libelle if bulletin.appreciation else "",
        "bulletin": bulletin,
    }

    html = render_to_string(
        "bulletins/bulletin_primaire_trimestriel.html",
        context
    )

    out_dir = os.path.join(settings.MEDIA_ROOT, "bulletins")
    os.makedirs(out_dir, exist_ok=True)

    filename = f"bulletin_{eleve.id}_T{bulletin.trimestre.numero}.pdf"
    filepath = os.path.join(out_dir, filename)

    HTML(string=html).write_pdf(filepath)

    return filepath
