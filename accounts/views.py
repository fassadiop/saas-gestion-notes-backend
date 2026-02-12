from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from accounts.models import User
from accounts.serializers import AdminTenantSerializer, ParentCreateSerializer, ParentSerializer, UserSerializer, UserCreateSerializer, UserUpdateSerializer
from accounts.permissions import CanManageUsers, IsAdminSaaS, IsAdminTenant, IsAdminTenantOrDirecteur
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action

from django.contrib.auth import get_user_model
from accounts.models import Parent
from academics.models import Eleve
from core.permissions import IsAdminTenantOrDirecteur
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


User = get_user_model()


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [CanManageUsers]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer
    
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "tenant": user.tenant_id,
            "must_change_password": user.must_change_password,
        })
    
class AdminTenantViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminTenantSerializer
    permission_classes = [IsAdminSaaS]

    def get_queryset(self):
        return super().get_queryset().filter(
            role="ADMIN_TENANT"
        )

class TenantUserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAdminTenant]

    def get_queryset(self):
        return User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=["DIRECTEUR", "ENSEIGNANT", "PARENT"]
        )

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )

class PersonnelViewSet(ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAdminTenant]

    def get_queryset(self):
        return User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=["DIRECTEUR", "ENSEIGNANT", "PARENT"],
        )

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )

class DirecteurParentViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Parent.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("user").prefetch_related("eleves")

    def get_serializer_class(self):
        if self.action == "create":
            return ParentCreateSerializer
        return ParentSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        tenant = self.request.user.tenant

        # 1️⃣ Création User Parent
        user = User.objects.create_user(
            username=data["telephone"],
            first_name=data["prenom"],
            last_name=data["nom"],
            email=data["email"],
            role="PARENT",
            tenant=tenant,
            must_change_password=True,
        )

        # Mot de passe initial
        user.set_password("123456")  # ou logique métier
        user.save()

        # 2️⃣ Création Parent
        parent = Parent.objects.create(
            user=user,
            tenant=tenant
        )

        # 3️⃣ Liaison élèves
        eleves = Eleve.objects.filter(
            id__in=data.get("eleves", []),
            tenant=tenant
        )
        parent.eleves.set(eleves)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(status=201)

    @action(
        detail=True,
        methods=["post"],
        url_path="reset-password"
    )
    def reset_password(self, request, pk=None):
        parent = self.get_object()
        user = parent.user

        temp_password = get_random_string(8)

        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])

        return Response(
            {
                "detail": "Mot de passe réinitialisé",
                "temporary_password": temp_password,
            },
            status=status.HTTP_200_OK
        )

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password = request.data.get("password")

        if not new_password:
            return Response(
                {"detail": "Mot de passe requis"},
                status=400
            )

        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response(
                {"detail": e.messages},
                status=400
            )

        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        return Response({"detail": "Mot de passe modifié"})


class ParentViewSet(ModelViewSet):
    serializer_class = ParentSerializer
    http_method_names = ["get", "head", "options"]
    permission_classes = [IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Parent.objects.filter(
            tenant=self.request.user.tenant
        )
