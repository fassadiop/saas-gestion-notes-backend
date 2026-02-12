# academics/serializers.py

from rest_framework import serializers
from .models import AffectationClasse, AnneeScolaire, Composante, Eleve, Classe, Matiere, Bareme


class AnneeScolaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeScolaire
        fields = "__all__"
        read_only_fields = ("tenant",)

class ClasseSerializer(serializers.ModelSerializer):
    annee_libelle = serializers.CharField(
        source="annee.libelle", read_only=True
    )

    class Meta:
        model = Classe
        fields = (
            "id",
            "nom",
            "niveau",
            "annee",
            "annee_libelle",
        )

class EleveSerializer(serializers.ModelSerializer):
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = Eleve
        fields = "__all__"
        read_only_fields = ("tenant",)

    def get_nom_complet(self, obj):
        return f"{obj.prenom} {obj.nom}"

class ComposanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Composante
        fields = (
            "id",
            "nom",
            "type",
            "matiere",
            "actif",
        )


class MatiereSerializer(serializers.ModelSerializer):
    composantes = ComposanteSerializer(
        many=True,
        read_only=True,
        source="composante_set"
    )

    has_composantes = serializers.SerializerMethodField()
    composantes_count = serializers.SerializerMethodField()
    est_evaluable = serializers.SerializerMethodField()

    class Meta:
        model = Matiere
        fields = [
            "id",
            "nom",
            "ordre_affichage",
            "actif",
            "composantes",

            # 🔥 champs métier
            "has_composantes",
            "composantes_count",
            "est_evaluable",
            "type_evaluation",
        ]

    def get_has_composantes(self, obj):
        return obj.composante_set.exists()

    def get_composantes_count(self, obj):
        return obj.composante_set.count()

    def get_est_evaluable(self, obj):
        """
        Une matière est évaluable si :
        - elle a au moins une composante
        (ou une composante technique créée automatiquement)
        """
        return obj.composante_set.exists()


class BaremeSerializer(serializers.ModelSerializer):
    classe_nom = serializers.CharField(
        source="classe.nom",
        read_only=True
    )
    annee_nom = serializers.CharField(
        source="annee.libelle",
        read_only=True
    )
    composante_nom = serializers.CharField(
        source="composante.nom",
        read_only=True
    )
    matiere_nom = serializers.CharField(
        source="composante.matiere.nom",
        read_only=True
    )

    class Meta:
        model = Bareme
        fields = (
            "id",
            "classe",
            "classe_nom",
            "annee",
            "annee_nom",
            "composante",
            "composante_nom",
            "matiere",
            "matiere_nom",
            "valeur_max",   
        )

class AffectationClasseSerializer(serializers.ModelSerializer):
    classe_nom = serializers.CharField(
        source="classe.nom",
        read_only=True,
    )

    class Meta:
        model = AffectationClasse
        fields = (
            "id",
            "enseignant",
            "classe",
            "classe_nom",
        )

class ClasseDashboardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nom = serializers.CharField()
    niveau = serializers.CharField()
    matieres = serializers.ListField(child=serializers.CharField())


class ClasseSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classe
        fields = ["id", "nom"]


class MatiereSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Matiere
        fields = ["id", "nom"]
