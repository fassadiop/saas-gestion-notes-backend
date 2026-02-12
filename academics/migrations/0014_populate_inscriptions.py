from django.db import migrations


def create_initial_inscriptions(apps, schema_editor):
    Eleve = apps.get_model("academics", "Eleve")
    Inscription = apps.get_model("academics", "Inscription")
    AnneeScolaire = apps.get_model("academics", "AnneeScolaire")

    # Pour chaque tenant
    for eleve in Eleve.objects.all():

        # Trouver l'année active du tenant
        annee_active = AnneeScolaire.objects.filter(
            tenant=eleve.tenant,
            actif=True
        ).first()

        if not annee_active:
            continue  # sécurité si aucune année active

        # Créer inscription si elle n'existe pas déjà
        Inscription.objects.get_or_create(
            eleve=eleve,
            annee=annee_active,
            tenant=eleve.tenant,
            defaults={
                "classe": eleve.classe,
                "actif": True
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0013_inscription"),
    ]

    operations = [
        migrations.RunPython(create_initial_inscriptions),
    ]
