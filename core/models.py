from django.db import models

class Tenant(models.Model):
    nom = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    localisation = models.CharField(max_length=255, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom


class TenantModel(models.Model):
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="%(class)s_set"
    )

    class Meta:
        abstract = True


