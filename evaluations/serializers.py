from rest_framework import serializers
from academics.serializers import EleveSerializer
from evaluations.models import Bulletin, Trimestre, Note
from .models import DecisionConseil, Note, Appreciation
from academics.models import Bareme

class DecisionConseilSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionConseil
        fields = [
            "decision",
            "mention",
            "commentaire",
            "autorise_examen",
            "date_decision"
        ]

class BulletinReadSerializer(serializers.ModelSerializer):
    eleve_detail = serializers.SerializerMethodField()
    decision = DecisionConseilSerializer(read_only=True)
    trimestre_numero = serializers.IntegerField(
        source="trimestre.numero",
        read_only=True
    )

    class Meta:
        model = Bulletin
        fields = "__all__"

    def get_eleve_detail(self, obj):
        return {
            "id": obj.eleve.id,
            "nom": obj.eleve.nom,
            "prenom": obj.eleve.prenom,
            "classe": obj.eleve.classe.nom
        }

# core/serializers.py

class TrimestreSerializer(serializers.ModelSerializer):
    annee_nom = serializers.CharField(
        source="annee.libelle",
        read_only=True
    )

    class Meta:
        model = Trimestre
        fields = [
            "id",
            "numero",
            "annee",
            "annee_nom",
            "date_debut",
            "date_fin",
            "actif",
            "cloture",
        ]

    def validate(self, data):
        request = self.context.get("request")
        user = request.user

        tenant = user.tenant if not user.is_superuser else data.get("tenant")
        annee = data.get("annee")
        numero = data.get("numero")

        if Trimestre.objects.filter(
            tenant=tenant,
            annee=annee,
            numero=numero
        ).exists():
            raise serializers.ValidationError(
                f"Le trimestre {numero} existe déjà pour cette année."
            )

        return data


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
                composante = obj.matiere.composante_set.filter(
                    tenant=obj.tenant
                ).first()

                if not composante:
                    return None

                bareme = Bareme.objects.get(
                    tenant=obj.tenant,
                    composante=composante,
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
    decision = DecisionConseilSerializer(read_only=True)

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
            "notes",
            "decision"
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
        source="eleve.nom",
        read_only=True
    )

    eleve_prenom = serializers.CharField(
        source="eleve.prenom",
        read_only=True
    )
    
    eleve_id = serializers.IntegerField(
    source="eleve.id",
    read_only=True
    )

    classe = serializers.CharField(
        source="eleve.classe.nom",
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
            "eleve_id",
            "eleve_nom",
            "eleve_prenom",
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


# 🔥 ENUM CENTRALISÉ
APPRECIATION_CHOICES = [
    "Excellent",
    "Bien",
    "Assez bien",
    "Passable",
    "Insuffisant",
]


class AppreciationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Appreciation
        fields = [
            "id",
            "libelle",
            "moyenne_min",
            "moyenne_max",
        ]

    # 🔒 VALIDATION LIBELLÉ
    def validate_libelle(self, value):
        if value not in APPRECIATION_CHOICES:
            raise serializers.ValidationError(
                "Libellé invalide"
            )
        return value

    # 🔒 VALIDATION MÉTIER
    def validate(self, data):
        tenant = self.context["request"].user.tenant

        libelle = data.get("libelle")
        min_val = data.get("moyenne_min")
        max_val = data.get("moyenne_max")

        # 🔥 min < max
        if min_val >= max_val:
            raise serializers.ValidationError(
                "moyenne_min doit être inférieur à moyenne_max"
            )

        # 🔥 éviter doublon libellé par tenant
        if Appreciation.objects.filter(
            tenant=tenant,
            libelle=libelle
        ).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError(
                "Cette appréciation existe déjà"
            )

        # 🔥 éviter chevauchement d’intervalles
        overlaps = Appreciation.objects.filter(
            tenant=tenant,
            moyenne_min__lte=max_val,
            moyenne_max__gte=min_val
        )

        if self.instance:
            overlaps = overlaps.exclude(id=self.instance.id)

        if overlaps.exists():
            raise serializers.ValidationError(
                "Intervalle chevauche une autre appréciation"
            )

        return data