from rest_framework import serializers
from processor.models import MultipleGarnPriorityOrders, State, GarnishmentType


class MultipleGarnPriorityOrderCRUDSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for MultipleGarnPriorityOrders that accepts state name/code and
    garnishment type name instead of IDs, while storing the related IDs.
    """
    state = serializers.CharField(source='state.state')
    garnishment_type = serializers.CharField(source='garnishment_type.type')

    class Meta:
        model = MultipleGarnPriorityOrders
        fields = [
            'id', 'state', 'garnishment_type', 'priority_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Resolve state by name or code
        state_payload = attrs.get('state')
        state_name = None
        if isinstance(state_payload, dict):
            state_name = state_payload.get('state')
        elif isinstance(state_payload, str):
            state_name = state_payload

        if not state_name:
            raise serializers.ValidationError("state is required")

        state_obj = State.objects.filter(state__iexact=state_name).first() or \
                    State.objects.filter(state_code__iexact=state_name).first()
        if not state_obj:
            raise serializers.ValidationError(f"State '{state_name}' not found")

        # Resolve garnishment type by name
        garnishment_payload = attrs.get('garnishment_type') or attrs.get('garnishment')
        garnishment_name = None
        if isinstance(garnishment_payload, dict):
            garnishment_name = garnishment_payload.get('type') or garnishment_payload.get('garnishment')
        elif isinstance(garnishment_payload, str):
            garnishment_name = garnishment_payload

        if not garnishment_name:
            raise serializers.ValidationError("garnishment is required")

        garnishment_obj = GarnishmentType.objects.filter(type__iexact=garnishment_name).first()
        if not garnishment_obj:
            raise serializers.ValidationError(f"GarnishmentType '{garnishment_name}' not found")

        # Replace nested inputs with actual model instances
        attrs['state'] = state_obj
        attrs['garnishment_type'] = garnishment_obj
        # Clean helper keys if present
        attrs.pop('garnishment', None)
        return attrs

    def create(self, validated_data):
        return MultipleGarnPriorityOrders.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
