from django.db import transaction
from academics.models import Matiere, Composante


@transaction.atomic
def desactiver_matiere(*, matiere: Matiere):
    matiere.actif = False
    matiere.save(update_fields=["actif"])

    Composante.objects.filter(
        matiere=matiere
    ).update(actif=False)
