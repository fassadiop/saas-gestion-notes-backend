from academics.models import AffectationClasse
from academics.models import AnneeScolaire


def est_enseignant_affecte_a_classe(
    *,
    enseignant,
    classe_id,
    tenant,
    annee=None
) -> bool:
    """
    Vérifie si un enseignant est affecté à une classe
    pour une année scolaire donnée (ou active par défaut).
    """

    if not annee:
        annee = AnneeScolaire.objects.filter(
            tenant=tenant,
            actif=True
        ).first()

    if not annee:
        return False

    return AffectationClasse.objects.filter(
        enseignant=enseignant,
        classe_id=classe_id,
        annee=annee,
        tenant=tenant,
    ).exists()
