# evaluations/services/pdf.py

import os
import base64
import qrcode
from io import BytesIO
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
from evaluations.models import Appreciation
from evaluations.services.annuel import calculer_moyenne_annuelle
from evaluations.services.classements import get_rang_annuel

def image_base64(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
    
def generate_qr_base64(url):
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def generer_bulletin_pdf(*, bulletin):
    eleve = bulletin.eleve
    classe = eleve.classe
    annee = classe.annee

    lignes = getattr(bulletin, "details_matiere", [])

    appreciations = Appreciation.objects.filter(
        tenant=bulletin.tenant
    ).order_by("-moyenne_min")

    moyenne_annuelle = None

    if bulletin.trimestre.numero == 3:
        moyenne_annuelle = calculer_moyenne_annuelle(
            tenant=bulletin.tenant,
            eleve=bulletin.eleve,
            annee=bulletin.trimestre.annee
        )

    rang_annuel = None

    if bulletin.trimestre.numero == 3:
        rang_annuel = get_rang_annuel(
            tenant=bulletin.tenant,
            eleve=bulletin.eleve,
            classe=bulletin.eleve.classe,
            annee=bulletin.trimestre.annee
        )

    decision = getattr(bulletin, "decision", None)

    signature_base64 = None

    if bulletin.tenant.signature_directeur:
        signature_base64 = image_base64(
            bulletin.tenant.signature_directeur.path
        )

    base_url = "http://localhost:5173"  # ⚠️ adapte prod

    verification_url = f"{base_url}/verify/bulletin/{bulletin.verification_token}"

    qr_code_base64 = generate_qr_base64(verification_url)

    context = {
        # 🔥 IMAGES BASE64
        "drapeau_sn_base64": image_base64(
            os.path.join(settings.BASE_DIR, "static", "images", "drapeau_sn.png")
        ),
        "logo_men_base64": image_base64(
            os.path.join(settings.BASE_DIR, "static", "images", "logo-men.png")
        ),

        # 🔥 DONNÉES BULLETIN
        "academie": bulletin.tenant.academie.nom if bulletin.tenant.academie else "",
        "inspection": bulletin.tenant.inspection.nom if bulletin.tenant.inspection else "",
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
        "rang_annuel": rang_annuel,
        "appreciations": [
            {
                "libelle": a.libelle,
                "active": bulletin.appreciation_id == a.id
            }
            for a in appreciations
        ],
        "moyenne_annuelle": moyenne_annuelle,
        "decision_conseil": decision.decision if decision else None,
        "mention": decision.mention if decision else None,
        "commentaire": decision.commentaire if decision else None,
        "bulletin": bulletin,
        "signature_directeur_base64": signature_base64,
        "qr_code_base64": qr_code_base64,
        "verification_url": verification_url,
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
