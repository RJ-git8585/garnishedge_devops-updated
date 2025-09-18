
from rest_framework import serializers
from user_app.models import SDU, GarnishmentOrder
from processor.models.shared_model.state import State

class StateNameField(serializers.PrimaryKeyRelatedField):
    """
    Custom field to accept state name and convert to State instance.
    """
    def to_internal_value(self, data):
        try:
            # Accept either state name or abbreviation 
            state = State.objects.filter(state__iexact=data).first() or State.objects.filter(abbreviation__iexact=data).first()
            if not state:
                raise serializers.ValidationError(f"State '{data}' not found.")
            return state
        except Exception:
            raise serializers.ValidationError(f"State '{data}' not found.")

    def to_representation(self, value):
        # Return the state name for output
        return value.state if value else None


class SDUSerializer(serializers.ModelSerializer):
    # Accept state name (or abbreviation) and convert to State instance
    state = serializers.SlugRelatedField(
        slug_field='state',  
        queryset=State.objects.all()
    )

    class Meta:
        model = SDU
        fields = ['id', 'name', 'state', 'order', 'country', 'fips_code', 'is_active']

    def validate_order(self, value):
        """
        Ensure the order exists in the GarnishmentOrder table.
        """
        if not GarnishmentOrder.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Order not found.")
        return value