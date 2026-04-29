from rest_framework import serializers
from .models import Departement, Region, Tenant
from .models import Academie, Inspection

class TenantSerializer(serializers.ModelSerializer):
    academie_nom = serializers.CharField(source="academie.nom", read_only=True)
    inspection_nom = serializers.CharField(source="inspection.nom", read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "nom",
            "code",
            "localisation",
            "type",
            "actif",
            "date_creation",
            "academie",
            "inspection",

            # 🔥 AJOUTS
            "academie_nom",
            "inspection_nom",
        ]
        read_only_fields = ("id", "date_creation")


class AcademieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Academie
        fields = "__all__"


class InspectionSerializer(serializers.ModelSerializer):
    academie_nom = serializers.CharField(
        source="academie.nom", read_only=True
    )

    class Meta:
        model = Inspection
        fields = "__all__"

class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "nom"]

class DepartementSerializer(serializers.ModelSerializer):
    region_nom = serializers.CharField(source="region.nom", read_only=True)

    class Meta:
        model = Departement
        fields = ["id", "nom", "region", "region_nom"]