# config/evaluations/services/notes.py

from django.db import transaction
from django.core.exceptions import ValidationError
from evaluations.models import Note

@transaction.atomic
def creer_ou_modifier_note(*, tenant, eleve, composante, trimestre, valeur):
    note, created = Note.objects.get_or_create(
        tenant=tenant,
        eleve=eleve,
        composante=composante,
        trimestre=trimestre,
        defaults={"valeur": valeur},
    )
    if not created:
        note.valeur = valeur

    note.full_clean()
    note.save()
    return note
