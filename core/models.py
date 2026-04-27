# config/core/models.py

from django.db import models

class Tenant(models.Model):
    nom = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    localisation = models.CharField(max_length=255, blank=True)

    signature_directeur = models.ImageField(
        upload_to="signatures/",
        null=True,
        blank=True
    )

    academie = models.ForeignKey(
        "core.Academie",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    inspection = models.ForeignKey(
        "core.Inspection",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    type = models.CharField(
        max_length=50,
        choices=(
            ("PUBLIC", "École publique"),
            ("PRIVE", "École privée"),
        ),
        default="PUBLIC"
    )

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

class Academie(models.Model):
    nom = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    region = models.CharField(max_length=100)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


class Inspection(models.Model):
    nom = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    departement = models.CharField(max_length=100)
    academie = models.ForeignKey(
        Academie,
        on_delete=models.CASCADE,
        related_name="inspections"
    )

    def __str__(self):
        return f"{self.nom} ({self.academie})"
    
class Region(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom
    
class Departement(models.Model):
    nom = models.CharField(max_length=100)
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name="departements"
    )

    class Meta:
        ordering = ["nom"]
        unique_together = ("nom", "region")

    def __str__(self):
        return f"{self.nom} ({self.region.nom})"
    

class Message(models.Model):
    TYPE_CHOICES = [
        ("DIRECTION", "Direction"),
        ("PARENT", "Parent"),
    ]

    titre = models.CharField(max_length=255)
    contenu = models.TextField()

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    # Optionnel mais IMPORTANT pour ton use case
    classe = models.ForeignKey(
        "academics.Classe",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages"
    )

    # Multi-tenant (cohérent avec ton archi)
    tenant = models.ForeignKey(
        "Tenant",
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre