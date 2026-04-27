from academics.models import Note, Bareme, Matiere
from django.db.models import Q


def calcul_moyenne_matiere(
    *, eleve, trimestre, matiere, tenant
) -> float | None:
    """
    Retourne la moyenne /10 pour UNE matière sur un trimestre.
    """

    # =========================
    # CAS DIRECT
    # =========================
    if matiere.type_evaluation == "DIRECTE":
        note = (
            Note.objects.filter(
                tenant=tenant,
                eleve=eleve,
                trimestre=trimestre,
                matiere=matiere,
            ).first()
        )

        if not note:
            return None

        try:
            bareme = Bareme.objects.get(
                tenant=tenant,
                matiere=matiere,
                classe=eleve.classe,
                annee=trimestre.annee,
            )
        except Bareme.DoesNotExist:
            return None

        return round((note.valeur / bareme.valeur_max) * 10, 2)

    # =========================
    # CAS PAR COMPOSANTE
    # =========================
    notes = (
        Note.objects.filter(
            tenant=tenant,
            eleve=eleve,
            trimestre=trimestre,
            composante__matiere=matiere,
        ).select_related("composante")
    )

    if not notes.exists():
        return None

    total = 0
    count = 0

    for n in notes:
        bareme = Bareme.objects.get(
            tenant=tenant,
            composante=n.composante,
            classe=eleve.classe,
            annee=trimestre.annee,
        )
        total += (n.valeur / bareme.valeur_max) * 10
        count += 1

    return round(total / count, 2)

def calcul_moyenne_generale(
    *, eleve, trimestre, tenant
) -> float | None:
    matieres = Matiere.objects.filter(
        tenant=tenant,
        actif=True,
    )

    total = 0
    count = 0

    for matiere in matieres:
        m = calcul_moyenne_matiere(
            eleve=eleve,
            trimestre=trimestre,
            matiere=matiere,
            tenant=tenant,
        )
        if m is not None:
            total += m
            count += 1

    if count == 0:
        return None

    return round(total / count, 2)
