from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    TYPE_CHOICES = [
        ("BULLETIN_PUBLIE", "Bulletin publié"),
        ("NOTE_AJOUTEE", "Note ajoutée"),
        ("DOCUMENT_VALIDE", "Document validé"),
        ("DOCUMENT_REJETE", "Document rejeté"),
        ("DECISION_CONSEIL", "Décision conseil"),
    ]

    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    reference_id = models.IntegerField()
    reference_type = models.CharField(max_length=100)

    tenant_id = models.IntegerField()  # aligné avec ton SaaS

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.reference_type} ({self.reference_id})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)

    titre = models.CharField(max_length=255)
    message = models.TextField()

    is_read = models.BooleanField(default=False)

    tenant_id = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "tenant_id"]),
            models.Index(fields=["event"]),
        ]

    def __str__(self):
        return f"{self.titre} → {self.user}"