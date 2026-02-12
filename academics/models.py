from django.db import models
from django.forms import ValidationError
from config import settings
from core.models import TenantModel, Tenant
from rest_framework import serializers

class Classe(TenantModel):
    annee = models.ForeignKey(
        "academics.AnneeScolaire",
        on_delete=models.CASCADE,
        related_name="classes"
    )
    nom = models.CharField(max_length=50)
    niveau = models.CharField(max_length=20)
    effectif_prevu = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("tenant", "annee", "nom")

    def __str__(self):
        return f"{self.nom} ({self.annee})"

class Eleve(TenantModel):
    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name="eleves"
    )
    matricule = models.CharField(max_length=30)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    sexe = models.CharField(
        max_length=1,
        choices=(("M", "Masculin"), ("F", "Féminin"))
    )
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("tenant", "matricule")
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"
    
    def get_classe_actuelle(self):
        inscription = self.inscriptions.filter(actif=True).first()
        if inscription:
            return inscription.classe
        return self.classe


class Matiere(TenantModel):
    TYPE_EVALUATION_CHOICES = [
        ("PAR_COMPOSANTE", "Par composante"),
        ("DIRECTE", "Directe"),
    ]

    nom = models.CharField(max_length=100)
    ordre_affichage = models.PositiveIntegerField()
    actif = models.BooleanField(default=True)

    type_evaluation = models.CharField(
        max_length=20,
        choices=TYPE_EVALUATION_CHOICES,
        default="PAR_COMPOSANTE",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.nom

class Composante(TenantModel):
    nom = models.CharField(max_length=50)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=(("RESSOURCE","Ressource"),("COMPETENCE","Compétence")))
    actif = models.BooleanField(default=True)


class Bareme(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE
    )

    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE
    )

    annee = models.ForeignKey(
        "academics.AnneeScolaire",
        on_delete=models.CASCADE
    )

    # 🔹 NOUVEAU : barème matière directe
    matiere = models.ForeignKey(
        Matiere,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    # 🔹 EXISTANT : barème par composante
    composante = models.ForeignKey(
        Composante,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    valeur_max = models.PositiveIntegerField()

    def clean(self):
        if self.matiere and self.composante:
            raise ValidationError(
                "Un barème ne peut pas être lié à une matière ET une composante."
            )
        if not self.matiere and not self.composante:
            raise ValidationError(
                "Un barème doit être lié soit à une matière soit à une composante."
            )
    class Meta:
            constraints = [
                # 🔒 PAR_COMPOSANTE
                models.UniqueConstraint(
                    fields=["tenant", "classe", "annee", "composante"],
                    condition=models.Q(composante__isnull=False),
                    name="uniq_bareme_par_composante",
                ),
                # 🔒 DIRECTE
                models.UniqueConstraint(
                    fields=["tenant", "classe", "annee", "matiere"],
                    condition=models.Q(matiere__isnull=False),
                    name="uniq_bareme_par_matiere",
                ),
            ]

class AnneeScolaire(TenantModel):
    libelle = models.CharField(max_length=9)  # ex: 2024-2025
    date_debut = models.DateField()
    date_fin = models.DateField()
    actif = models.BooleanField(default=False)

    class Meta:
        unique_together = ("tenant", "libelle")
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.libelle}"

class AffectationClasse(models.Model):
    enseignant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "ENSEIGNANT"},
        related_name="affectations_classes"
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        related_name="affectations_enseignants",
    )
    # Quand tout sera OK 
    # annee = models.ForeignKey(
    #     AnneeScolaire,
    #     on_delete=models.CASCADE,
    # )
    annee = models.ForeignKey(
        AnneeScolaire,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = (
            "enseignant",
            "classe",
            "annee",
            "tenant",
        )

    def __str__(self):
        return f"{self.enseignant} → {self.classe}"



class AffectationEnseignant(models.Model):
    enseignant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "ENSEIGNANT"},
        related_name="affectations"
    )
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (
            "enseignant",
            "classe",
            "matiere",
            "annee",
            "tenant",
        )

    def __str__(self):
        return f"{self.enseignant} - {self.classe} - {self.matiere}"


class Inscription(models.Model):
    eleve = models.ForeignKey(
        "Eleve",
        on_delete=models.CASCADE,
        related_name="inscriptions"
    )

    classe = models.ForeignKey(
        "Classe",
        on_delete=models.PROTECT,
        related_name="inscriptions"
    )

    annee = models.ForeignKey(
        "AnneeScolaire",
        on_delete=models.PROTECT,
        related_name="inscriptions"
    )

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="inscriptions"
    )

    date_inscription = models.DateField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("eleve", "annee", "tenant")

    def __str__(self):
        return f"{self.eleve} - {self.annee}"
