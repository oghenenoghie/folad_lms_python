from rest_framework import serializers

from .models import Guardian


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            "public_id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "occupation",
            "address",
            "is_active",
        ]
