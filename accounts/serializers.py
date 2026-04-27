# config/accounts/serializers.py

from datetime import date

from rest_framework import serializers
from django.contrib.auth import get_user_model

from rest_framework import serializers
from accounts.models import Parent, UserScope
from academics.models import Eleve
from evaluations.models import Bulletin

User = get_user_model()

class UserScopeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    class Meta:
        model = UserScope
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    scopes = UserScopeSerializer(many=True, read_only=True)
    inspection_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "cni",
            "role",
            "is_active",
            "scopes",
            "inspection_nom",
        )
        read_only_fields = ("id",)
        
    def get_inspection_nom(self, obj):
        scope = obj.scopes.filter(
            inspection__isnull=False,
            actif=True
        ).first()

        return scope.inspection.nom if scope else None

    def perform_create(self, serializer):
        user = self.request.user

        # 🔥 ADMIN TENANT → on force le tenant
        if getattr(user, "role", None) == "ADMIN_TENANT":
            serializer.save(tenant=self.context["request"].user.tenant)

        # 🔥 ADMIN SAAS → libre
        else:
            serializer.save()
    
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        # 🔥 mise à jour explicite de tous les champs
        instance.username = validated_data.get("username", instance.username)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.email = validated_data.get("email", instance.email)
        instance.telephone = validated_data.get("telephone", instance.telephone)
        instance.cni = validated_data.get("cni", instance.cni)
        instance.role = validated_data.get("role", instance.role)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

class UserCreateSerializer(serializers.ModelSerializer):
    inspection_id = serializers.IntegerField(required=False, write_only=True)
    academie_id = serializers.IntegerField(required=False, write_only=True)
    password = serializers.CharField(write_only=True)
    tenant_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "role",
            "password",
            "tenant_id",
            "inspection_id",
            "academie_id",
        )

    def validate(self, attrs):
        creator = self.context["request"].user
        role = attrs.get("role")
        tenant_id = attrs.get("tenant_id")

        inspection_id = self.initial_data.get("inspection_id")
        academie_id = self.initial_data.get("academie_id")

        # 🔥 ADMIN IEF
        if role == "ADMIN_IEF" and not inspection_id:
            raise serializers.ValidationError(
                "Une inspection est obligatoire pour ADMIN_IEF."
            )

        # 🔥 ADMIN ACADEMIE
        if role == "ADMIN_ACADEMIE" and not academie_id:
            raise serializers.ValidationError(
                "Une académie est obligatoire pour ADMIN_ACADEMIE."
            )

        # ❌ sécurité
        if role == "ADMIN_SAAS":
            raise serializers.ValidationError(
                "Création d’ADMIN_SAAS interdite via l’API."
            )

        # ================= ADMIN SAAS =================
        if creator.role == "ADMIN_SAAS":

            # 🔥 autoriser tous les rôles sauf ADMIN_SAAS
            allowed_roles = [
                "ADMIN_TENANT",
                "ADMIN_IEF",
                "ADMIN_ACADEMIE",
                "ADMIN_NATIONAL",
            ]

            if role not in allowed_roles:
                raise serializers.ValidationError(
                    "Rôle non autorisé pour ADMIN_SAAS."
                )

            # 🔥 tenant obligatoire seulement pour ADMIN_TENANT
            if role == "ADMIN_TENANT" and not tenant_id:
                raise serializers.ValidationError(
                    "tenant_id obligatoire pour ADMIN_TENANT."
                )

        # ================= ADMIN TENANT =================
        elif creator.role == "ADMIN_TENANT":

            if role not in ("DIRECTEUR", "ENSEIGNANT", "PARENT"):
                raise serializers.ValidationError(
                    "ADMIN_TENANT ne peut créer que Directeur, Enseignant ou Parent."
                )

            if tenant_id:
                raise serializers.ValidationError(
                    "ADMIN_TENANT ne peut pas fournir tenant_id."
                )

        else:
            raise serializers.ValidationError(
                "Vous n'avez pas les droits pour créer des utilisateurs."
            )

        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop("tenant_id", None)
        inspection_id = validated_data.pop("inspection_id", None)
        academie_id = validated_data.pop("academie_id", None)
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)

        creator = self.context["request"].user

        # ================= ADMIN SAAS =================
        if creator.role == "ADMIN_SAAS":

            if user.role == "ADMIN_TENANT":
                user.tenant_id = tenant_id
            else:
                user.tenant = None

            user.is_staff = True

        else:
            user.tenant = creator.tenant

        # 🔥 SAUVEGARDE AVANT FK
        user.save()

        # 🔥 SCOPE IEF
        if user.role == "ADMIN_IEF" and inspection_id:
            UserScope.objects.create(
                user=user,
                inspection_id=inspection_id,
                date_debut=date.today(),
                actif=True
            )

        # 🔥 SCOPE ACADEMIE
        if user.role == "ADMIN_ACADEMIE" and academie_id:
            UserScope.objects.create(
                user=user,
                academie_id=academie_id,
                date_debut=date.today(),
                actif=True
            )

        return user
    
class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "cni",
            "role",
            "password",
            "is_active",
        )

    def validate(self, attrs):
        user = self.context["request"].user
        target = self.instance

        # ADMIN_TENANT ne peut modifier que son personnel
        if user.role == "ADMIN_TENANT":
            if target.tenant != user.tenant:
                raise serializers.ValidationError("Accès interdit.")

        # Interdiction de modifier le rôle ADMIN_SAAS
        if target.role == "ADMIN_SAAS":
            raise serializers.ValidationError(
                "Modification ADMIN_SAAS interdite."
            )

        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # 🔐 changement de mot de passe UNIQUEMENT si fourni
        if password:
            instance.set_password(password)

        instance.save()
        return instance


class AdminTenantSerializer(serializers.ModelSerializer):
    tenant_nom = serializers.CharField(
        source="tenant.nom", read_only=True
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "is_active",
            "tenant",
            "tenant_nom",
        )

class ParentCreateSerializer(serializers.Serializer):
    prenom = serializers.CharField()
    nom = serializers.CharField()
    email = serializers.EmailField()
    telephone = serializers.CharField()
    cni = serializers.CharField()

    eleves = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

class ParentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "username", "telephone", "cni"]
        extra_kwargs = {
            "username": {"required": False},
        }

class ParentDashboardSerializer(serializers.Serializer):
    eleve_id = serializers.IntegerField()
    eleve_nom = serializers.CharField()
    eleve_prenom = serializers.CharField()
    classe = serializers.CharField()

    moyenne_actuelle = serializers.FloatField()
    rang = serializers.IntegerField()
    effectif = serializers.IntegerField()

    evolution_moyenne = serializers.ListField(
        child=serializers.FloatField()
    )

    matieres = serializers.ListField()
    alertes = serializers.ListField(child=serializers.CharField())
    activites = serializers.ListField(child=serializers.CharField())
    
class EleveSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Eleve
        fields = ["id", "prenom", "nom"]

class BulletinParentSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.SerializerMethodField()

    class Meta:
        model = Bulletin
        fields = [
            "id",
            "eleve_nom",
            "trimestre",
            "moyenne_sur_10",
            "rang",
            "date_generation",
            "notes",
        ]

    def get_eleve_nom(self, obj):
        if not obj.eleve:
            return "-"
        return f"{obj.eleve.prenom} {obj.eleve.nom}"

class ParentSerializer(serializers.ModelSerializer):
    user = ParentUserSerializer()

    eleves = EleveSimpleSerializer(many=True, read_only=True)

    eleves_ids = serializers.PrimaryKeyRelatedField(
        queryset=Eleve.objects.all(),
        many=True,
        write_only=True,
        source="eleves"
    )

    class Meta:
        model = Parent
        fields = ["id", "user", "eleves", "eleves_ids"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        eleves = validated_data.pop("eleves", None)

        # 🔥 update user
        if user_data:
            user = instance.user

            for attr, value in user_data.items():
                setattr(user, attr, value)

            # 🔥 clé métier
            if "telephone" in user_data:
                user.username = user_data["telephone"]

            user.save()

        # 🔥 update eleves
        if eleves is not None:
            instance.eleves.set(eleves)

        instance.save()
        return instance
    
    def create(self, validated_data):
        user_data = validated_data.pop("user")
        eleves = validated_data.pop("eleves", [])

        # 🔥 username = téléphone
        username = user_data.get("telephone")

        user = User.objects.create(
            username=username,
            **user_data
        )

        user.set_password("123456")
        user.save()

        parent = Parent.objects.create(
            user=user,
            tenant=self.context["request"].user.tenant
        )

        parent.eleves.set(eleves)

        return parent