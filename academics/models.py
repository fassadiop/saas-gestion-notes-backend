# config/academics/models.py

import uuid
import os
from core.models import TenantModel
from django.conf import settings
from django.db import models
from django.forms import ValidationError
from core.models import Departement, TenantModel, Tenant
from django.db.models import Q

class Classe(TenantModel):

    NIVEAU_SYSTEME = (
        ("ELEMENTAIRE", "Élémentaire"),
        ("COLLEGE", "Collège"),
        ("LYCEE", "Lycée"),
    )
    annee = models.ForeignKey(
        "academics.AnneeScolaire",
        on_delete=models.CASCADE,
        related_name="classes"
    )
    nom = models.CharField(max_length=50)
    niveau = models.CharField(max_length=20)
    niveau_systeme = models.CharField(
        max_length=20,
        choices=NIVEAU_SYSTEME,
        default="ELEMENTAIRE"
    )
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
    ine = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )
    matricule = models.CharField(max_length=30)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    sexe = models.CharField(
        max_length=1,
        choices=(("M", "Masculin"), ("F", "Féminin"))
    )

    departement = models.ForeignKey(
        Departement,
        on_delete=models.PROTECT,
        related_name="eleves",
        null=True,
        blank=True
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

    def clean(self):
        if self.matiere and self.composante:
            raise ValidationError(
                "Un barème ne peut pas être lié à une matière ET une composante."
            )
        if not self.matiere and not self.composante:
            raise ValidationError(
                "Un barème doit être lié soit à une matière soit à une composante."
            )
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
        constraints = [
            models.UniqueConstraint(
                fields=["enseignant", "classe", "matiere", "annee", "tenant"],
                name="uniq_affect_ens"  # <= 30
            ),
        ]

        indexes = [
            models.Index(
                fields=["enseignant", "classe", "tenant"],
                name="idx_affect_ens_cls_tnt"
            ),
            models.Index(
                fields=["matiere", "classe", "tenant"],
                name="idx_affect_mat_cls_tnt"
            ),
        ]

    def __str__(self):
        return f"{self.enseignant} - {self.classe} - {self.matiere}"
    
    def clean(self):
        if self.classe.tenant != self.tenant:
            raise ValidationError("Tenant incohérent")

        if self.annee and self.annee.tenant != self.tenant:
            raise ValidationError("Année invalide")


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
        ordering = ["-date_inscription"]

        constraints = [
            models.UniqueConstraint(
                fields=["eleve", "annee"],
                condition=Q(actif=True),
                name="unique_active_inscription_per_eleve"
            )
        ]

        indexes = [
            models.Index(fields=["tenant", "annee"]),
            models.Index(fields=["eleve", "actif"]),
        ]

    def __str__(self):
        return f"{self.eleve} - {self.annee}"

    def save(self, *args, **kwargs):
        if not self.tenant:
            raise ValueError("Tenant obligatoire")
        super().save(*args, **kwargs)


def upload_path(instance, filename):
    ext = filename.split('.')[-1]
    new_name = f"{uuid.uuid4()}.{ext}"
    return f"tenant_{instance.tenant_id}/eleves/{instance.eleve_id}/{new_name}"


class DocumentEleve(TenantModel):
    TYPE_CHOICES = (
        ("ACTE", "Acte de naissance"),
        ("CERTIFICAT", "Certificat médical"),
        ("PHOTO", "Photo identité"),
        ("AUTRE", "Autre"),
    )

    STATUT_CHOICES = (
        ("EN_ATTENTE", "En attente"),
        ("VALIDE", "Validé"),
        ("REJETE", "Rejeté"),
    )

    eleve = models.ForeignKey(
        "academics.Eleve",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    parent = models.ForeignKey(
        "accounts.Parent",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    titre = models.CharField(max_length=255)

    nom_original = models.CharField(
        max_length=255,
        blank=True
    )

    fichier = models.FileField(
        upload_to=upload_path
    )

    type_document = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    extension = models.CharField(
        max_length=10,
        blank=True
    )

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="EN_ATTENTE"
    )

    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents_valides"
    )

    date_validation = models.DateTimeField(
        null=True,
        blank=True
    )

    date_upload = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-date_upload"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["eleve"]),
            models.Index(fields=["parent"]),
        ]

    def clean(self):
        # Sécurité métier : vérifier que le parent est bien lié à l'élève
        if not self.parent.eleves.filter(id=self.eleve.id).exists():
            raise ValidationError("Cet élève n'est pas lié à ce parent")

    def save(self, *args, **kwargs):
        # 🔒 Validation métier
        self.clean()

        # 🔥 Extraction des métadonnées fichier
        if self.fichier:
            filename = self.fichier.name
            self.extension = os.path.splitext(filename)[1].replace(".", "").lower()

            # garder le vrai nom original si pas déjà défini
            if not self.nom_original:
                self.nom_original = filename

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titre} - {self.eleve}"