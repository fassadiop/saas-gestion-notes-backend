from evaluations.models import Note

def build_bulletin_details(bulletin):
    notes = (
        Note.objects
        .filter(
            tenant=bulletin.tenant,
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre,
        )
        .select_related("matiere", "composante")
    )

    lignes = []

    for note in notes:
        if note.matiere:
            lignes.append({
                "type": "MATIERE",
                "libelle": note.matiere.libelle,
                "valeur": note.valeur,
            })
        elif note.composante:
            lignes.append({
                "type": "COMPOSANTE",
                "libelle": note.composante.nom,  # ✔️ correct
                "valeur": note.valeur,
            })

    bulletin.details_matiere = lignes
    return bulletin
