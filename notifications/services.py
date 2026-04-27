from .models import Event, Notification
from django.contrib.auth import get_user_model

User = get_user_model()


def create_event(type, reference_id, reference_type, tenant_id):
    event = Event.objects.create(
        type=type,
        reference_id=reference_id,
        reference_type=reference_type,
        tenant_id=tenant_id
    )

    dispatch_notifications(event)

    return event


def dispatch_notifications(event):
    if event.type == "BULLETIN_PUBLIE":
        notify_parents(event, "📢 Bulletin publié", "Le bulletin de votre enfant est disponible.")

    elif event.type == "NOTE_AJOUTEE":
        notify_parents(event, "📝 Nouvelle note", "Une nouvelle note a été ajoutée.")

    elif event.type == "DOCUMENT_VALIDE":
        notify_parents(event, "🧾 Document validé", "Votre document a été validé.")

    elif event.type == "DOCUMENT_REJETE":
        notify_parents(event, "❌ Document rejeté", "Votre document a été rejeté.")

    elif event.type == "DECISION_CONSEIL":
        notify_parents(event, "🎓 Décision du conseil", "Une décision a été prise pour votre enfant.")


def notify_parents(event, titre, message):
    from academics.models import Eleve

    try:
        eleve = Eleve.objects.get(id=event.reference_id)
    except Eleve.DoesNotExist:
        return

    parents = eleve.parents.filter(tenant_id=eleve.tenant_id)

    # 🔥 récupérer tous les user_id concernés
    user_ids = [p.user_id for p in parents if p.user_id]

    # 🔥 récupérer les notifications existantes en une seule requête
    existing_user_ids = set(
        Notification.objects.filter(
            user_id__in=user_ids,
            event__type=event.type,
            event__reference_id=event.reference_id
        ).values_list("user_id", flat=True)
    )

    notifications = []

    for parent in parents:
        if parent.user_id is None:
            continue

        if parent.user_id in existing_user_ids:
            continue

        notifications.append(
            Notification(
                user=parent.user,
                event=event,
                titre=titre,
                message=message,
                tenant_id=eleve.tenant_id
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)