from rest_framework import serializers
from academics.serializers import EleveSerializer
from evaluations.models import Bulletin, Trimestre, Note
from .models import Note
from academics.models import Bareme

class BulletinReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bulletin
        fields = "__all__"
        read_only_fields = (
            "statut",
            "total_points",
            "total_max",
            "moyenne_sur_10",
            "rang",
            "date_generation",
        )


class TrimestreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trimestre
        fields = ("id", "numero")


class NoteSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(
        source="eleve.nom_complet",
        read_only=True,
    )

    bareme_max = serializers.SerializerMethodField()
    matiere_nom = serializers.CharField(
        source="matiere.nom",
        read_only=True,
    )
    composante_nom = serializers.CharField(
        source="composante.nom",
        read_only=True,
    )

    class Meta:
        model = Note
        fields = (
            "id",
            "eleve",
            "eleve_nom",
            "matiere",
            "matiere_nom",
            "composante",
            "composante_nom",
            "trimestre",
            "valeur",
            "bareme_max",
        )

    def get_bareme_max(self, obj):
        try:
            if obj.composante:
                bareme = Bareme.objects.get(
                    tenant=obj.tenant,
                    composante=obj.composante,
                    classe=obj.eleve.classe,
                    annee=obj.trimestre.annee,
                )
            else:
                bareme = Bareme.objects.get(
                    tenant=obj.tenant,
                    matiere=obj.matiere,
                    classe=obj.eleve.classe,
                    annee=obj.trimestre.annee,
                )
            return bareme.valeur_max
        except Bareme.DoesNotExist:
            return None


class BulletinNoteSerializer(serializers.ModelSerializer):
    composante = serializers.CharField(source="composante.nom")

    class Meta:
        model = Note
        fields = [
            "id",
            "composante",
            "valeur"
        ]

class BulletinDetailSerializer(serializers.ModelSerializer):
    eleve = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()

    class Meta:
        model = Bulletin
        fields = [
            "id",
            "eleve",
            "total_points",
            "total_max",
            "moyenne_sur_10",
            "rang",
            "observation",
            "statut",
            "notes"
        ]

    def get_eleve(self, bulletin):
        return {
            "id": bulletin.eleve.id,
            "nom": bulletin.eleve.nom,
            "prenom": bulletin.eleve.prenom,
            "classe": bulletin.eleve.classe.nom
        }

    def get_notes(self, bulletin):
        notes = Note.objects.filter(
            eleve=bulletin.eleve,
            trimestre=bulletin.trimestre,
            tenant=bulletin.tenant
        ).select_related("composante", "composante__matiere")

        return BulletinNoteSerializer(notes, many=True).data
    

class BulletinParentSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(
        source="eleve.nom_complet",
        read_only=True
    )
    classe = serializers.CharField(
        source="eleve.classe.libelle",
        read_only=True
    )
    trimestre = serializers.CharField(
        source="trimestre.get_numero_display",
        read_only=True
    )

    notes = serializers.SerializerMethodField()

    class Meta:
        model = Bulletin
        fields = (
            "id",
            "eleve_nom",
            "classe",
            "trimestre",
            "moyenne_sur_10",
            "rang",
            "date_generation",
            "notes",
        )

    def get_notes(self, obj):
        qs = (
            Note.objects.filter(
                tenant=obj.tenant,
                eleve=obj.eleve,
                trimestre__annee=obj.trimestre.annee,
                trimestre__numero=obj.trimestre.numero,
            )
            .select_related("matiere", "composante")
        )

        return NoteParentSerializer(qs, many=True).data


class NoteParentSerializer(serializers.ModelSerializer):
    libelle = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = (
            "libelle",
            "type",
            "valeur",
        )

    def get_libelle(self, obj):
        if obj.matiere:
            return obj.matiere.nom   # ou le vrai champ
        if obj.composante:
            return obj.composante.nom
        return ""

    def get_type(self, obj):
        return "MATIERE" if obj.matiere else "COMPOSANTE"

