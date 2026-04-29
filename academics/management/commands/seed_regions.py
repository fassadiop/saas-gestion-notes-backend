from django.core.management.base import BaseCommand
from core.models import Region, Departement

class Command(BaseCommand):
    help = "Charge toutes les régions et départements du Sénégal"

    def handle(self, *args, **kwargs):
        data = [
            {
                "nom": "Dakar",
                "departements": ["Dakar", "Guédiawaye", "Pikine", "Rufisque"],
            },
            {
                "nom": "Thiès",
                "departements": ["Thiès", "Mbour", "Tivaouane"],
            },
            {
                "nom": "Saint-Louis",
                "departements": ["Saint-Louis", "Dagana", "Podor"],
            },
            {
                "nom": "Diourbel",
                "departements": ["Diourbel", "Bambey", "Mbacké"],
            },
            {
                "nom": "Fatick",
                "departements": ["Fatick", "Foundiougne", "Gossas"],
            },
            {
                "nom": "Kaolack",
                "departements": ["Kaolack", "Guinguinéo", "Nioro du Rip"],
            },
            {
                "nom": "Kaffrine",
                "departements": ["Kaffrine", "Birkilane", "Koungheul", "Malem Hodar"],
            },
            {
                "nom": "Kolda",
                "departements": ["Kolda", "Médina Yoro Foulah", "Vélingara"],
            },
            {
                "nom": "Ziguinchor",
                "departements": ["Ziguinchor", "Bignona", "Oussouye"],
            },
            {
                "nom": "Sédhiou",
                "departements": ["Sédhiou", "Bounkiling", "Goudomp"],
            },
            {
                "nom": "Tambacounda",
                "departements": ["Tambacounda", "Bakel", "Goudiry", "Koumpentoum"],
            },
            {
                "nom": "Kédougou",
                "departements": ["Kédougou", "Salémata", "Saraya"],
            },
            {
                "nom": "Louga",
                "departements": ["Louga", "Kébémer", "Linguère"],
            },
            {
                "nom": "Matam",
                "departements": ["Matam", "Kanel", "Ranérou"],
            },
        ]

        for region_data in data:
            region, _ = Region.objects.get_or_create(nom=region_data["nom"])

            for dep in region_data["departements"]:
                Departement.objects.get_or_create(
                    nom=dep,
                    region=region
                )

        self.stdout.write(self.style.SUCCESS("✔ Régions et départements chargés avec succès"))