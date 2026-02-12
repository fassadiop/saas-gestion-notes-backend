from rest_framework import serializers
from django.contrib.auth import get_user_model

from rest_framework import serializers
from accounts.models import Parent
from academics.models import Eleve

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "is_active",
        )
        read_only_fields = ("id",)

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    tenant_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "role", "password", "tenant_id")

    def validate(self, attrs):
        creator = self.context["request"].user
        role = attrs.get("role")
        tenant_id = attrs.get("tenant_id")

        if role == "ADMIN_SAAS":
            raise serializers.ValidationError(
                "Création d’ADMIN_SAAS interdite via l’API."
            )

        if creator.role == "ADMIN_SAAS":
            if role != "ADMIN_TENANT":
                raise serializers.ValidationError(
                    "ADMIN_SAAS ne peut créer que des ADMIN_TENANT."
                )
            if not tenant_id:
                raise serializers.ValidationError(
                    "tenant_id obligatoire."
                )

        if creator.role == "ADMIN_TENANT":
            if role not in ("DIRECTEUR", "ENSEIGNANT", "PARENT"):
                raise serializers.ValidationError(
                    "ADMIN_TENANT ne peut créer que Directeur, Enseignant ou Parent."
                )
            if tenant_id:
                raise serializers.ValidationError(
                    "ADMIN_TENANT ne peut pas fournir tenant_id."
                )

        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop("tenant_id", None)
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)

        creator = self.context["request"].user

        if creator.role == "ADMIN_SAAS":
            user.tenant_id = tenant_id
            user.is_staff = True
        else:
            user.tenant = creator.tenant

        user.save()
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
            "email",
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

    eleves = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

class ParentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "username"]


class ParentSerializer(serializers.ModelSerializer):
    user = ParentUserSerializer(read_only=True)
    eleves = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Parent
        fields = ["id", "user", "eleves"]