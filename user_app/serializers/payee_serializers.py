
from rest_framework import serializers
from user_app.models import PayeeDetails, GarnishmentOrder
from processor.models.shared_model.state import State

class StateNameField(serializers.PrimaryKeyRelatedField):
    """
    Accepts state full name or state code (abbreviation) and returns a State instance.
    """
    def to_internal_value(self, data):
        try:
            normalized = (data or "").strip()
            # Accept either state name or state code (e.g., 'Alabama' or 'AL')
            state = (
                State.objects.filter(state__iexact=normalized).first()
                or State.objects.filter(state_code__iexact=normalized).first()
            )
            if not state:
                raise serializers.ValidationError(f"State '{data}' not found.")
            return state
        except Exception:
            raise serializers.ValidationError(f"State '{data}' not found.")

    def to_representation(self, value):
        # Return the state name for output; handle PKOnlyObject or raw PKs
        if value is None:
            return None
        # If we already have a State instance with 'state' attribute
        if hasattr(value, 'state'):
            return value.state
        # DRF may give a PKOnlyObject or a raw PK; resolve to name
        pk_value = getattr(value, 'pk', value)
        state = State.objects.filter(pk=pk_value).only('state').first()
        return state.state if state else pk_value


class PayeeSerializer(serializers.ModelSerializer):
    # Accept state name or code and convert to State instance
    state = StateNameField(queryset=State.objects.all())
    # Accept GarnishmentOrder by its case_id string
    case_id = serializers.SlugRelatedField(
        slug_field='case_id',
        queryset=GarnishmentOrder.objects.all()
    )

    class Meta:
        model = PayeeDetails
        fields = ['id', 'payee', 'state', 'case_id', 'address', 'contact', 'fips_code', 'is_active']



