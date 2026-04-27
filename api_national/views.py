# config/api_national/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from academics.models import Eleve
from evaluations.models import Bulletin


class ElevesNationauxView(APIView):
    def get(self, request):
        eleves = Eleve.objects.filter(ine__isnull=False)

        data = [
            {
                "ine": e.ine,
                "nom": e.nom,
                "prenom": e.prenom,
                "classe": e.get_classe_actuelle().nom if e.get_classe_actuelle() else None,
            }
            for e in eleves
        ]

        return Response(data)


class ResultatsNationauxView(APIView):
    def get(self, request):
        bulletins = Bulletin.objects.filter(statut="PUBLIE")

        data = [
            {
                "eleve": b.eleve.ine,
                "moyenne": b.moyenne_sur_10,
                "rang": b.rang,
            }
            for b in bulletins
        ]

        return Response(data)