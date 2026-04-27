# config/evaluations/models.py

from django.db import models
from django.conf import settings
from core.models import Tenant, TenantModel
from academics.models import Eleve, Composante, Matiere
from django.core.exceptions import ValidationError
from academics.models import AnneeScolaire, Eleve, Composante, Classe, Bareme
from django.core.exceptions import ValidationError
import uuid

class Trimestre(TenantModel):
    NUMERO_CHOICES = (
        (1, "1er trimestre"),
        (2, "2e trimestre"),
        (3, "3e trimestre"),
    )

    numero = models.PositiveSmallIntegerField(choices=NUMERO_CHOICES)

    annee = models.ForeignKey(
        AnneeScolaire,
        on_delete=models.CASCADE,
        related_name="trimestres"
    )

    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    actif = models.BooleanField(default=False)
    cloture = models.BooleanField(default=False)

    class Meta:
        unique_together = ("tenant", "annee", "numero")
        ordering = ["annee", "numero"]

    def __str__(self):
        return f"T{self.numero} - {self.annee}"
    
    #empêcher plusieurs trimestres actifs, plus tard
    # def clean(self):
    #     if self.date_fin <= self.date_debut:
    #         raise ValidationError("La date de fin doit être après la date de début")

    #     if self.cloture and self.actif:
    #         raise ValidationError("Un trimestre clôturé ne peut pas être actif")

    # def save(self, *args, **kwargs):
    #     self.clean()

    #     if self.actif:
    #         Trimestre.objects.filter(
    #             tenant=self.tenant,
    #             annee=self.annee,
    #             actif=True
    #         ).exclude(pk=self.pk).update(actif=False)

    #     super().save(*args, **kwargs)

class Note(TenantModel):
    valeur = models.FloatField()

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    trimestre = models.ForeignKey(Trimestre, on_delete=models.CASCADE)

    # 🔹 CAS PAR COMPOSANTE (existant)
    composante = models.ForeignKey(
        Composante,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    # 🔹 CAS DIRECT (nouveau)
    matiere = models.ForeignKey(
        Matiere,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            # 🔒 unicité PAR_COMPOSANTE
            models.UniqueConstraint(
                fields=["tenant", "eleve", "composante", "trimestre"],
                condition=models.Q(composante__isnull=False),
                name="uniq_note_par_composante",
            ),
            # 🔒 unicité DIRECTE
            models.UniqueConstraint(
                fields=["tenant", "eleve", "matiere", "trimestre"],
                condition=models.Q(matiere__isnull=False),
                name="uniq_note_directe",
            ),
        ]

    def clean(self):
        from academics.models import Bareme

        # 🔐 cohérence cible
        if self.composante and self.matiere:
            raise ValidationError(
                "Une note ne peut pas cibler une composante ET une matière."
            )

        if not self.composante and not self.matiere:
            raise ValidationError(
                "Une note doit cibler une composante ou une matière."
            )

        # 🔐 cohérence année
        if self.trimestre.annee != self.eleve.classe.annee:
            raise ValidationError(
                "Le trimestre n'appartient pas à l'année de la classe de l'élève."
            )

        # =========================
        # CAS PAR COMPOSANTE
        # =========================
        if self.composante:
            try:
                bareme = Bareme.objects.get(
                    tenant=self.tenant,
                    composante=self.composante,
                    classe=self.eleve.classe,
                    annee=self.trimestre.annee,
                )
            except Bareme.DoesNotExist:
                raise ValidationError(
                    "Aucun barème défini pour cette composante/classe/année."
                )

        # =========================
        # CAS DIRECT
        # =========================
        # CAS DIRECT → utiliser composante technique
        else:
            composante = self.matiere.composante_set.filter(
                tenant=self.tenant
            ).first()

            if not composante:
                raise ValidationError(
                    "Aucune composante technique pour cette matière."
                )

            try:
                bareme = Bareme.objects.get(
                    tenant=self.tenant,
                    composante=composante,
                    classe=self.eleve.classe,
                    annee=self.trimestre.annee,
                )
            except Bareme.DoesNotExist:
                raise ValidationError(
                    "Aucun barème défini pour cette matière/classe/année."
                )

        # 🔐 valeur ≤ barème
        if self.valeur < 0 or self.valeur > bareme.valeur_max:
            raise ValidationError(
                f"Note invalide : doit être comprise entre 0 et {bareme.valeur_max}."
            )


class Appreciation(TenantModel):
    libelle = models.CharField(max_length=50)
    moyenne_min = models.FloatField()
    moyenne_max = models.FloatField()
    

class Bulletin(models.Model):
    STATUTS_BULLETIN = (
        ("BROUILLON", "Brouillon"),
        ("VALIDE_ENSEIGNANT", "Validé par l’enseignant"),
        ("VALIDE_DIRECTEUR", "Validé par le directeur"),
        ("PUBLIE", "Publié"),
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    trimestre = models.ForeignKey(Trimestre, on_delete=models.CASCADE)

    total_points = models.FloatField(null=True, blank=True)
    total_max = models.FloatField(null=True, blank=True)
    moyenne_sur_10 = models.FloatField(null=True, blank=True)

    rang = models.IntegerField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    appreciation = models.ForeignKey(Appreciation, null=True, on_delete=models.SET_NULL)

    verification_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True
    )
   
    statut = models.CharField(
        max_length=30,
        choices=STATUTS_BULLETIN,
        default="BROUILLON"
    )

    date_generation = models.DateTimeField(null=True, blank=True)


    class Meta:
        unique_together = ("tenant", "eleve", "trimestre")

    
    def clean(self):
        if self.pk:
            ancien = Bulletin.objects.filter(pk=self.pk).values("statut").first()
            if ancien and ancien["statut"] == "PUBLIE" and self.statut != "PUBLIE":
                raise ValidationError({
                    "detail": "Bulletin déjà publié : modification interdite."
                })
            

class Validation(models.Model):
    ACTIONS = (
        ("VALIDE_ENSEIGNANT", "Validation enseignant"),
        ("VALIDE_DIRECTEUR", "Validation directeur"),
        ("PUBLIE", "Publication"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    bulletin = models.ForeignKey(
        Bulletin,
        on_delete=models.CASCADE,
        related_name="validations"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    action = models.CharField(max_length=30, choices=ACTIONS)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_action"]


class DecisionConseil(models.Model):
    DECISIONS = [
        ("PASSE_EN_CLASSE_SUPERIEURE", "Passe en classe supérieure"),
        ("RESERVE", "Passage avec réserve"),
        ("REDOUBLE", "Redoublement"),
        ("EXAMEN", "Présente examen"),
        ("NON_EXAMEN", "Non présenté à l’examen"),
        ("ORIENTATION", "Orientation spécifique"),
    ]

    MENTIONS = [
        ("FELICITATIONS", "Félicitations"),
        ("ENCOURAGEMENTS", "Encouragements"),
        ("AVERTISSEMENT", "Avertissement"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)

    bulletin = models.OneToOneField(
        "Bulletin",
        on_delete=models.CASCADE,
        related_name="decision"
    )

    decision = models.CharField(max_length=30, choices=DECISIONS)

    mention = models.CharField(
        max_length=20,
        choices=MENTIONS,
        null=True,
        blank=True
    )

    commentaire = models.TextField(null=True, blank=True)

    autorise_examen = models.BooleanField(default=False)

    # 🔒 traçabilité
    cree_par = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True
    )

    date_decision = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bulletin} - {self.decision}"