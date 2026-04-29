# academics/serializers.py

from rest_framework import serializers
from core.models import Departement
from .models import AffectationClasse, AnneeScolaire, Composante, DocumentEleve, Eleve, Classe, Matiere, Bareme, Inscription
from django.db.models import Q
from django.db import transaction
from accounts.models import User, Parent

from rest_framework.exceptions import ValidationError
import uuid
import random
import string
import mimetypes
from academics import models


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
        fields = "__all__" 

class EleveSerializer(serializers.ModelSerializer):
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = Eleve
        fields = "__all__"
        read_only_fields = ("tenant",)

    def get_nom_complet(self, obj):
        return f"{obj.prenom} {obj.nom}"
    
    def update(self, instance, validated_data):
        validated_data.pop("classe", None)
        validated_data.pop("classe_id", None)

        return super().update(instance, validated_data)
    


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
    matiere_nom = serializers.SerializerMethodField()

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

    def get_matiere_nom(self, obj):
        # 🔒 cas POST → obj = dict
        if isinstance(obj, dict):
            matiere = obj.get("matiere")
            composante = obj.get("composante")

            if matiere:
                return Matiere.objects.filter(id=matiere.id if hasattr(matiere, "id") else matiere).first().nom if matiere else None

            if composante:
                comp = Composante.objects.filter(
                    id=composante.id if hasattr(composante, "id") else composante
                ).select_related("matiere").first()
                return comp.matiere.nom if comp else None

            return None

        # 🔥 cas normal → instance Django
        if obj.matiere:
            return obj.matiere.nom

        if obj.composante:
            return obj.composante.matiere.nom

        return None
    
    def create(self, validated_data):
        instance = super().create(validated_data)
        return instance
    
    def validate(self, data):
        matiere = data.get("matiere")
        composante = data.get("composante")

        if matiere and composante:
            raise serializers.ValidationError(
                "Choisir soit matière soit composante"
            )

        if not matiere and not composante:
            raise serializers.ValidationError(
                "Matière ou composante obligatoire"
            )

        return data
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        # 🔒 instance peut être dict (POST)
        if isinstance(instance, dict):
            data["type"] = (
                "DIRECT"
                if instance.get("matiere")
                else "COMPOSANTE"
            )
        else:
            data["type"] = (
                "DIRECT"
                if instance.matiere
                else "COMPOSANTE"
            )

        return data

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

class ClasseSerializer(serializers.ModelSerializer):
    tenant = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Classe
        fields = "__all__"


class InscriptionCreateSerializer(serializers.Serializer):

    # ELEVE
    prenom = serializers.CharField()
    nom = serializers.CharField()
    date_naissance = serializers.DateField()
    sexe = serializers.ChoiceField(choices=[("M","Masculin"),("F","Féminin")])

    # LOCALISATION
    departement_id = serializers.IntegerField()

    # CLASSE
    classe_id = serializers.IntegerField()
    annee_id = serializers.IntegerField()

    # PARENT
    parent_prenom = serializers.CharField()
    parent_nom = serializers.CharField()
    parent_cni = serializers.CharField()
    parent_telephone = serializers.CharField()
    parent_email = serializers.EmailField(required=False, allow_null=True)

    def validate(self, data):
        tenant = self.context["request"].user.tenant

        nom = data["nom"]
        prenom = data["prenom"]
        date_naissance = data["date_naissance"]
        annee_id = data["annee_id"]

        # 🔍 chercher élève existant
        eleve = Eleve.objects.filter(
            tenant=tenant,
            nom=nom,
            prenom=prenom,
            date_naissance=date_naissance
        ).first()

        if eleve:
            # 🔍 vérifier inscription existante
            if Inscription.objects.filter(
                eleve=eleve,
                annee_id=annee_id
            ).exists():
                raise serializers.ValidationError(
                    "Cet élève est déjà inscrit pour cette année."
                )

        return data
    
    def to_representation(self, instance):
        eleve = getattr(instance, "eleve", None)

        return {
            "eleve": {
                "id": eleve.id if eleve else None,
                "nom": eleve.nom if eleve else None,
                "prenom": eleve.prenom if eleve else None,
            },
            "message": "Inscription réussie",
            "generated_password": self.context.get("generated_password"),
        }

    @transaction.atomic
    def create(self, validated_data):
        tenant = self.context["request"].user.tenant

        # 🔍 Vérifier parent existant
        user = User.objects.filter(
            tenant=tenant
        ).filter(
            Q(cni=validated_data["parent_cni"]) |
            Q(telephone=validated_data["parent_telephone"])
        ).first()

        if user:
            parent, _ = Parent.objects.get_or_create(
                user=user,
                tenant=tenant
            )
        else:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            user = User.objects.create(
                username=validated_data["parent_telephone"],
                first_name=validated_data["parent_prenom"],
                last_name=validated_data["parent_nom"],
                email=validated_data.get("parent_email"),
                role="PARENT",
                tenant=tenant,
                cni=validated_data["parent_cni"],
                telephone=validated_data["parent_telephone"],
                must_change_password=True
            )
            user.set_password(password)
            user.save()

            parent, _ = Parent.objects.get_or_create(
                user=user,
                tenant=tenant
            )

        # 🔍 Classe
        try:
            classe = Classe.objects.get(id=validated_data["classe_id"], tenant=tenant)
        except Classe.DoesNotExist:
            raise ValidationError("Classe invalide")

        # 🔍 Année
        try:
            annee = AnneeScolaire.objects.get(id=validated_data["annee_id"], tenant=tenant)
        except AnneeScolaire.DoesNotExist:
            raise ValidationError("Année invalide")

        departement = Departement.objects.get(
            id=validated_data["departement_id"]
        )

        # 🎓 ELEVE
        eleve, created = Eleve.objects.get_or_create(
            tenant=tenant,
            nom=validated_data["nom"],
            prenom=validated_data["prenom"],
            date_naissance=validated_data["date_naissance"],
            defaults={
                "matricule": f"ELV-{uuid.uuid4().hex[:8].upper()}",
                "sexe": validated_data["sexe"],
                "departement": departement,
                "classe": classe,
            }
        )

        # 📝 Nouvelle inscription
        inscription, created = Inscription.objects.get_or_create(
            eleve=eleve,
            annee=annee,
            tenant=tenant,
            defaults={
                "classe": classe,
                "actif": True
            }
        )

        if not created:
            raise ValidationError(
                "Cet élève est déjà inscrit pour cette année."
            )
        
        # 🔗 Lien parent
        parent.eleves.add(eleve)

        return inscription
    
class InscriptionListSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(source="eleve.nom")
    eleve_prenom = serializers.CharField(source="eleve.prenom")
    classe_nom = serializers.CharField(source="classe.nom")
    annee = serializers.CharField(source="annee.libelle")

    class Meta:
        model = Inscription
        fields = [
            "id",
            "eleve_nom",
            "eleve_prenom",
            "classe_nom",
            "annee",
            "date_inscription",
            "actif"
        ]

class InscriptionDetailSerializer(serializers.ModelSerializer):

    eleve_nom = serializers.CharField(source="eleve.nom", read_only=True)
    eleve_prenom = serializers.CharField(source="eleve.prenom", read_only=True)
    sexe = serializers.CharField(source="eleve.sexe", read_only=True)
    date_naissance = serializers.DateField(source="eleve.date_naissance", read_only=True)

    parent_nom = serializers.SerializerMethodField()
    parent_prenom = serializers.SerializerMethodField()
    parent_telephone = serializers.SerializerMethodField()
    parent_email = serializers.SerializerMethodField()

    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    annee = serializers.CharField(source="annee.libelle", read_only=True)

    class Meta:
        model = Inscription
        fields = "__all__"

    def get_parent(self, obj):
        return obj.eleve.parents.first()

    def get_parent_nom(self, obj):
        parent = self.get_parent(obj)
        return parent.user.last_name if parent else None

    def get_parent_prenom(self, obj):
        parent = self.get_parent(obj)
        return parent.user.first_name if parent else None

    def get_parent_telephone(self, obj):
        parent = self.get_parent(obj)
        return parent.user.telephone if parent and parent.user else None

    def get_parent_email(self, obj):
        parent = self.get_parent(obj)
        return parent.user.email if parent and parent.user else None


class DocumentEleveSerializer(serializers.ModelSerializer):
    # 🔥 Nom élève (affichage frontend)
    eleve_nom = serializers.SerializerMethodField()

    # 🔥 MIME type (preview intelligent)
    content_type = serializers.SerializerMethodField()

    class Meta:
        model = DocumentEleve
        fields = "__all__"
        read_only_fields = ("parent", "tenant", "date_upload")

    def get_eleve_nom(self, obj):
        return f"{obj.eleve.nom} {obj.eleve.prenom}"

    def get_content_type(self, obj):
        type_guess, _ = mimetypes.guess_type(obj.fichier.name)
        return type_guess