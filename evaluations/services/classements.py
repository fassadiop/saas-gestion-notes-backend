# config/evaluations/services/classements.py

from evaluations.models import Bulletin
from evaluations.services.annuel import calculer_moyenne_annuelle
from academics.models import Eleve


def recalculer_rangs(*, tenant, classe, trimestre):
    bulletins = (
        Bulletin.objects
        .filter(
            tenant=tenant,
            eleve__classe=classe,
            trimestre=trimestre
        )
        .order_by("-moyenne_sur_10")
    )

    rang = 0
    last_moyenne = None
    compteur = 0

    for bulletin in bulletins:
        compteur += 1
        if bulletin.moyenne_sur_10 != last_moyenne:
            rang = compteur
            last_moyenne = bulletin.moyenne_sur_10

        bulletin.rang = rang
        bulletin.save(update_fields=["rang"])


def calculer_rangs_annuels(*, tenant, classe, annee):
    """
    Classement annuel basé sur moyenne annuelle
    (même logique que recalculer_rangs)
    """

    eleves = Eleve.objects.filter(
        tenant_id=tenant.id,
        classe=classe
    )

    data = []

    for eleve in eleves:
        moyenne = calculer_moyenne_annuelle(
            tenant=tenant,
            eleve=eleve,
            annee=annee
        )

        if moyenne is not None:
            data.append({
                "eleve": eleve,
                "moyenne": moyenne
            })

    # 🔥 EXACTEMENT la même logique que trimestriel
    data.sort(key=lambda x: x["moyenne"], reverse=True)

    rang = 0
    last_moyenne = None
    compteur = 0

    for item in data:
        compteur += 1

        if item["moyenne"] != last_moyenne:
            rang = compteur
            last_moyenne = item["moyenne"]

        item["rang"] = rang

    return data

def get_rang_annuel(*, tenant, eleve, classe, annee):
    data = calculer_rangs_annuels(
        tenant=tenant,
        classe=classe,
        annee=annee
    )

    for item in data:
        if item["eleve"].id == eleve.id:
            return item["rang"]

    return None