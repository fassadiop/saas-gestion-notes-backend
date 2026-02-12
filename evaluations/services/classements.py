# config/evaluations/services/classements.py

from evaluations.models import Bulletin


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
