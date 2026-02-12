# config/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from config import settings
from core.models import Tenant, TenantModel

class User(AbstractUser):
    ROLE_CHOICES = (
        ("ADMIN_SAAS", "Administrateur SaaS"),
        ("ADMIN_TENANT", "Administrateur Établissement"),
        ("DIRECTEUR", "Directeur"),
        ("ENSEIGNANT", "Enseignant"),
        ("PARENT", "Parent"),
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
        return f"{self.user.get_full_name()} ({self.telephone})"
