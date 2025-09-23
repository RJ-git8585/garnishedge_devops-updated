from rest_framework import serializers
from processor.models import State, PayPeriod
from user_app.models import PEO ,Client


# ---------- Custom Field Types ----------
class PEOField(serializers.Field):
    def to_representation(self, value: PEO):
        return value.peo_id if value else None

    def to_internal_value(self, data):
        try:
            return PEO.objects.get(peo_id=data)
        except PEO.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"PEO with id '{data}' not found"})


class StateField(serializers.Field):
    def to_representation(self, value: State):
        return value.state_code if value else None

    def to_internal_value(self, data):
        try:
            return State.objects.get(state_code__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"State '{data}' not found"})


class PayPeriodField(serializers.Field):
    def to_representation(self, value: PayPeriod):
        return value.name if value else None

    def to_internal_value(self, data):
        try:
            return PayPeriod.objects.get(name__iexact=data)
        except PayPeriod.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"PayPeriod '{data}' not found"})


# ---------- Serializer ----------
class ClientSerializer(serializers.ModelSerializer):
    """
    Serializer for Client model.
    - GET: returns human-readable PEO ID, state code, and pay period name.
    - POST/PUT: accepts natural keys (same fields, not *_id).
    """

    peo = PEOField()
    state = StateField()
    pay_period = PayPeriodField()

    class Meta:
        model = Client
        fields = [
            "id",
            "client_id",
            "peo",
            "state",
            "pay_period",
            "legal_name",
            "dba",
            "service_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")
