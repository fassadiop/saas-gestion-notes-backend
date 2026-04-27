# config/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import Tenant, TenantModel, Inspection, Academie

from django.conf import settings
from django.core.exceptions import ValidationError

class User(AbstractUser):
    ROLE_CHOICES = (
        ("ADMIN_SAAS", "Administrateur SaaS"),
        ("ADMIN_TENANT", "Administrateur Établissement"),
        ("ADMIN_NATIONAL", "Administrateur National"),
        ("ADMIN_IEF", "Administrateur de l'IEF"),
        ("ADMIN_ACADEMIE", "Administrateur de l'Académie"),
        ("DIRECTEUR", "Directeur"),
        ("ENSEIGNANT", "Enseignant"),
        ("PARENT", "Parent"),
    )
    # Enlever "null=True, blank=True" une fois que les user sont à jour
    cni = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telephone = models.CharField(max_length=20, unique=True, null=True, blank=True)

    signature = models.ImageField(
        upload_to="signatures/",
        null=True,
        blank=True
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Parent(TenantModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_profile"
    )
    eleves = models.ManyToManyField(
        "academics.Eleve",
        related_name="parents",
        blank=True
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.telephone})"


class UserScope(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scopes"
    )

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    academie = models.ForeignKey(
        Academie,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # 🔥 temporel
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)

    actif = models.BooleanField(default=True)

    def clean(self):
        if not self.inspection and not self.academie:
            raise ValidationError("Un scope doit avoir une inspection ou une académie")

        if self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError("date_fin invalide")

    def __str__(self):
        return f"{self.user} - scope"