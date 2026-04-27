from academics.models import Bareme


def get_bareme_max_par_composante(
    *, tenant, composante, classe, annee
) -> int:
    bareme = Bareme.objects.get(
        tenant=tenant,
        composante=composante,
        classe=classe,
        annee=annee,
    )
    return bareme.valeur_max


def get_bareme_max_par_matiere(*, tenant, matiere, classe, annee) -> int:
    bareme = Bareme.objects.get(
        tenant=tenant,
        matiere=matiere,
        classe=classe,
        annee=annee,
    )
    return bareme.valeur_max
