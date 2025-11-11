
from rest_framework import serializers
from user_app.models import PayeeDetails, PayeeAddress, GarnishmentOrder
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


class PayeeAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for PayeeAddress nested within PayeeSerializer.
    """
    # Accept state name or code and convert to State instance
    state = StateNameField(queryset=State.objects.all())
    
    class Meta:
        model = PayeeAddress
        fields = ['address_1', 'address_2', 'city', 'state', 'zip_code', 'zip_plus_4']


class PayeeSerializer(serializers.ModelSerializer):
    # Map id to payee_id for API consistency
    id = serializers.IntegerField(source='payee_id', read_only=True)
    # Accept GarnishmentOrder by its case_id string
    case_id = serializers.SlugRelatedField(
        slug_field='case_id',
        queryset=GarnishmentOrder.objects.all()
    )
    # Nested address serializer
    address = PayeeAddressSerializer(required=False, allow_null=True)

    class Meta:
        model = PayeeDetails
        fields = [
            'id', 'payee_id', 'payee_type', 'payee', 'case_id',
            'routing_number', 'bank_account', 'case_number_required',
            'case_number_format', 'fips_required', 'fips_length',
            'last_used', 'is_active', 'created_at', 'updated_at', 'address'
        ]
        read_only_fields = ['id', 'payee_id', 'created_at', 'updated_at']

    def create(self, validated_data):
        """
        Create PayeeDetails and associated PayeeAddress.
        """
        address_data = validated_data.pop('address', None)
        payee = PayeeDetails.objects.create(**validated_data)
        
        if address_data:
            PayeeAddress.objects.create(payee=payee, **address_data)
        
        return payee

    def update(self, instance, validated_data):
        """
        Update PayeeDetails and associated PayeeAddress.
        """
        address_data = validated_data.pop('address', None)
        
        # Update PayeeDetails fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update or create PayeeAddress
        if address_data is not None:
            address_instance, created = PayeeAddress.objects.get_or_create(
                payee=instance,
                defaults=address_data
            )
            if not created:
                for attr, value in address_data.items():
                    setattr(address_instance, attr, value)
                address_instance.save()
        
        return instance

    def to_representation(self, instance):
        """
        Custom representation to include nested address data.
        """
        representation = super().to_representation(instance)
        
        # Include address data if it exists
        # For OneToOneField, accessing when it doesn't exist raises RelatedObjectDoesNotExist
        try:
            address = instance.address
            representation['address'] = PayeeAddressSerializer(address).data
        except (PayeeAddress.DoesNotExist, AttributeError):
            representation['address'] = None
        
        return representation

