# config/analytics/models/py

from django.db import models
from academics.models import AnneeScolaire
from core.models import Academie


class StatistiqueAcademique(models.Model):
    academie = models.ForeignKey(
        Academie,
        on_delete=models.CASCADE,
        related_name="stats"
    )

    annee = models.ForeignKey(
        AnneeScolaire,
        on_delete=models.CASCADE
    )

    moyenne_generale = models.FloatField(default=0)
    taux_reussite = models.FloatField(default=0)
    effectif_total = models.IntegerField(default=0)

    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("academie", "annee")