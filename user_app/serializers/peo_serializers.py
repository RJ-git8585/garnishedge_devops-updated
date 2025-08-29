from rest_framework import serializers
from user_app.models import PEO
from processor.models import State


class PEOSerializer(serializers.ModelSerializer):
    """
    Serializer for PEO model.
    - Read: returns human-readable fields.
    - Write: accepts state_code for foreign key.
    """

    # ---------- Read-only (for GET) ----------
    state = serializers.CharField(source="state.state_code", read_only=True)

    # ---------- Write-only (for POST/PUT/PATCH) ----------
    state_code = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = PEO
        fields = [
            "id",
            # read-only
            "state",
            # write-only
            "state_code",
            # common fields
            "peo_id",
            "name",
            "contact_person",
            "tax_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")

    # ---------- Helpers ----------
    def _resolve_related(self, state_code):
        errors, state = {}, None

        if state_code:
            try:
                state = State.objects.get(state_code__iexact=state_code)
            except State.DoesNotExist:
                errors["state_code"] = f"State '{state_code}' not found"

        if errors:
            raise serializers.ValidationError(errors)

        return state

    # ---------- CRUD ----------
    def create(self, validated_data):
        state_code = validated_data.pop("state_code")
        state = self._resolve_related(state_code)

        return PEO.objects.create(state__iexact=state, **validated_data)

    def update(self, instance, validated_data):
        state_code = validated_data.pop("state_code", None)

        if state_code:
            state = self._resolve_related(state_code)
            if state:
                instance.state = state

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
