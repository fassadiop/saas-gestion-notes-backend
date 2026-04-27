# config/accounts/views.py

from rest_framework import status
from django.utils.crypto import get_random_string
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from accounts.models import User, UserScope
from accounts.serializers import AdminTenantSerializer, ParentCreateSerializer, ParentSerializer, UserSerializer, UserCreateSerializer, UserUpdateSerializer
from accounts.permissions import CanManageUsers, IsAdminSaaS, IsAdminTenant, IsAdminTenantOrDirecteur, IsAdminTenantOrSaaS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action

from django.contrib.auth import get_user_model
from accounts.models import Parent
from academics.models import Eleve
from evaluations.models import Bulletin, Note
from core.permissions import IsAdminTenantOrDirecteur
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from accounts.serializers import UserScopeSerializer
from notifications.models import Notification


User = get_user_model()


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [CanManageUsers]

    def get_queryset(self):
        user = self.request.user

        if user.role == "ADMIN_SAAS":
            return User.objects.all().order_by("-id")

        if user.role == "ADMIN_TENANT":
            return User.objects.filter(
                tenant=user.tenant
            ).order_by("-id")

        return User.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer
    
    def perform_create(self, serializer):
        user = self.request.user

        # 🔥 ADMIN TENANT → on force le tenant
        if getattr(user, "role", None) == "ADMIN_TENANT":
            serializer.save(tenant=user.tenant)

        # 🔥 ADMIN SAAS → libre
        else:
            serializer.save()

class UserScopeViewSet(ModelViewSet):
    queryset = UserScope.objects.all().order_by("-id")
    serializer_class = UserScopeSerializer
    permission_classes = [IsAuthenticated, IsAdminSaaS]
    
    
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
    serializer_class = AdminTenantSerializer
    permission_classes = [IsAdminTenantOrSaaS]

    def get_queryset(self):
        user = self.request.user

        if user.role == "ADMIN_SAAS":
            return User.objects.filter(role="ADMIN_TENANT")

        if user.role == "ADMIN_TENANT":
            return User.objects.filter(
                role="ADMIN_TENANT",
                tenant=user.tenant
            )

        return User.objects.none()
    
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
        user = self.request.user

        qs = User.objects.filter(tenant=user.tenant)

        if self.action == "list":
            qs = qs.filter(role__in=["DIRECTEUR", "ENSEIGNANT"])

        return qs

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant
        )

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            print("USING UserUpdateSerializer")
            return UserUpdateSerializer

        print("USING UserSerializer")
        return UserSerializer

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
    permission_classes = [IsAdminTenantOrDirecteur]

    def get_queryset(self):
        return Parent.objects.filter(
            tenant=self.request.user.tenant
        )


class ParentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 🔥 récupérer le parent
        parent = user.parent_profile

        eleve_id = request.query_params.get("eleve_id")

        # 🔥 élèves du parent
        eleves = parent.eleves.all()

        if eleve_id:
            eleves = eleves.filter(id=eleve_id)

        data = []

        for eleve in eleves:

            # =========================
            # BULLETINS (base du système)
            # =========================
            bulletins = Bulletin.objects.filter(
                eleve=eleve
            ).order_by("trimestre__annee", "trimestre__numero")

            if not bulletins.exists():
                continue

            dernier = bulletins.last()

            # =========================
            # ÉVOLUTION
            # =========================
            evolution = [
                float(b.moyenne_sur_10) for b in bulletins
            ]

            # =========================
            # MATIÈRES (via notes)
            # =========================
            notes = Note.objects.filter(
                eleve=eleve,
                trimestre=dernier.trimestre
            ).select_related("matiere")

            matieres = []

            for n in notes:
                if n.matiere:
                    matieres.append({
                        "nom": n.matiere.nom,
                        "moyenne": float(n.valeur)
                    })

            # =========================
            # ALERTES (simple v1)
            # =========================
            alertes = []

            if len(evolution) >= 2:
                if evolution[-1] < evolution[-2]:
                    alertes.append("Baisse de la moyenne générale")

            faibles = [m for m in matieres if m["moyenne"] < 5]
            if faibles:
                alertes.append("Matières faibles détectées")

            # =========================
            # ACTIVITÉS (notifications)
            # =========================
            activites = list(
                Notification.objects.filter(
                    user=user,
                    tenant_id=user.tenant_id
                )
                .order_by("-created_at")
                .values_list("message", flat=True)[:5]
            )

            # =========================
            # EFFECTIF (approximation)
            # =========================
            classe = eleve.get_classe_actuelle()

            effectif = Bulletin.objects.filter(
                eleve__classe=classe,
                trimestre=dernier.trimestre
            ).count()

            data.append({
                "eleve_id": eleve.id,
                "eleve_nom": eleve.nom,
                "eleve_prenom": eleve.prenom,
               "classe": str(classe),

                "moyenne_actuelle": float(dernier.moyenne_sur_10),
                "rang": dernier.rang,
                "effectif": effectif,

                "evolution_moyenne": evolution,
                "matieres": matieres,
                "alertes": alertes,
                "activites": activites
            })

        return Response(data)
