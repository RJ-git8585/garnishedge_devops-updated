from rest_framework import serializers
from processor.models import State, PayPeriod
from user_app.models import PEO ,Client


class ClientSerializer(serializers.ModelSerializer):
    """
    Common serializer for Client model.
    - Read: returns human-readable fields.
    - Write: accepts natural/business keys (peo_id, state_code, pay_period_name).
    """

    # ---------- Read-only (for GET) ----------
    peo = serializers.CharField(source="peo.peo_id", read_only=True)
    state = serializers.CharField(source="state.state_code", read_only=True)
    pay_period = serializers.CharField(source="pay_period.name", read_only=True)

    # ---------- Write-only (for POST/PUT/PATCH) ----------
    peo_id = serializers.CharField(write_only=True, required=True)
    state_code = serializers.CharField(write_only=True, required=True)
    pay_period_name = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "client_id",
            # read-only
            "peo", "state", "pay_period",
            # write-only
            "peo_id", "state_code", "pay_period_name",
            # common fields
            "legal_name",
            "dba",
            "industry_type",
            "tax_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")

    # ---------- Helpers ----------
    def _resolve_related(self, peo_id, state_code, pay_period_name):
        errors, peo, state, pay_period = {}, None, None, None

        if peo_id:
            try:
                peo = PEO.objects.get(peo_id=peo_id)
            except PEO.DoesNotExist:
                errors["peo_id"] = f"PEO with id '{peo_id}' not found"

        if state_code:
            try:
                state = State.objects.get(state_code__iexact=state_code)
            except State.DoesNotExist:
                errors["state_code"] = f"State '{state_code}' not found"

        if pay_period_name:
            try:
                pay_period = PayPeriod.objects.get(name__iexact=pay_period_name)
            except PayPeriod.DoesNotExist:
                errors["pay_period_name"] = f"PayPeriod '{pay_period_name}' not found"

        if errors:
            raise serializers.ValidationError(errors)

        return peo, state, pay_period

    # ---------- CRUD ----------
    def create(self, validated_data):
        peo_id = validated_data.pop("peo_id")
        state_code = validated_data.pop("state_code")
        pay_period_name = validated_data.pop("pay_period_name")

        peo, state, pay_period = self._resolve_related(peo_id, state_code, pay_period_name)

        return Client.objects.create(
            peo=peo, state=state, pay_period=pay_period, **validated_data
        )

    def update(self, instance, validated_data):
        peo_id = validated_data.pop("peo_id", None)
        state_code = validated_data.pop("state_code", None)
        pay_period_name = validated_data.pop("pay_period_name", None)

        if any([peo_id, state_code, pay_period_name]):
            peo, state, pay_period = self._resolve_related(peo_id, state_code, pay_period_name)
            if peo:
                instance.peo = peo
            if state:
                instance.state = state
            if pay_period:
                instance.pay_period = pay_period

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
