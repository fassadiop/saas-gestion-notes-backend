# evaluations/services/annuel.py

from evaluations.models import Bulletin


def calculer_moyenne_annuelle(*, tenant, eleve, annee):
    """
    Calcule la moyenne annuelle d’un élève
    """

    bulletins = Bulletin.objects.filter(
        tenant_id=tenant.id,
        eleve=eleve,
        trimestre__annee=annee
    )

    moyennes = [
        b.moyenne_sur_10
        for b in bulletins
        if b.moyenne_sur_10 is not None
    ]

    if len(moyennes) == 0:
        return None

    return round(sum(moyennes) / len(moyennes), 2)