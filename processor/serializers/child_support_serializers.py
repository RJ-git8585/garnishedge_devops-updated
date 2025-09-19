from rest_framework import serializers
from processor.models import *

class WithholdingRulesSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)
    
    class Meta:
        model = WithholdingRules
        fields = ['state', 'rule', 'allocation_method', 'withholding_limit']

class WithholdingRulesCRUDSerializer(serializers.ModelSerializer):
    """
    Serializer for CRUD on WithholdingRules that accepts state name/code as input
    and stores the related State id. Returns state name in responses.
    """
    state = serializers.CharField(source='state.state')

    class Meta:
        model = WithholdingRules
        fields = [
            'id', 'state', 'rule', 'allocation_method', 'withholding_limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Resolve state by name or code
        state_payload = attrs.get('state') or {}
        state_name = None
        if isinstance(state_payload, dict):
            state_name = state_payload.get('state')
        elif isinstance(state_payload, str):
            state_name = state_payload

        if state_name:
            try:
                state_obj = State.objects.filter(state__iexact=state_name).first()
                if not state_obj:
                    state_obj = State.objects.filter(state_code__iexact=state_name).first()
                if not state_obj:
                    raise serializers.ValidationError(f"State '{state_name}' not found")
                attrs['state'] = state_obj
            except Exception as exc:
                raise serializers.ValidationError(str(exc))
        return attrs

    def create(self, validated_data):
        return WithholdingRules.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class WithholdingLimitSerializer(serializers.ModelSerializer):
    # Get fields from the related WithholdingRules model
    rule_id = serializers.CharField(source='rule.rule', read_only=True)  # This gets the 'rule' field value from WithholdingRules
    state = serializers.CharField(source='rule.state.state', read_only=True)  # Assuming State model has 'state' field
    allocation_method = serializers.CharField(source='rule.allocation_method', read_only=True)
    withholding_limit = serializers.CharField(source='rule.withholding_limit', read_only=True)
    
    class Meta:
        model = WithholdingLimit
        fields = [
            'state', 
            'rule_id', 
            'allocation_method', 
            'withholding_limit', 
            'wl', 
            'supports_2nd_family', 
            'arrears_of_more_than_12_weeks', 
            'number_of_orders', 
            'weekly_de_code'
        ]


class WithholdingLimitCRUDSerializer(serializers.ModelSerializer):
    """
    Serializer for CRUD on WithholdingLimit that accepts:
    - state (name or code) and rule_number to resolve FK to WithholdingRules
    Returns state name and rule_id in responses.
    """
    state = serializers.CharField(source='rule.state.state')
    rule_number = serializers.IntegerField(write_only=True, required=True)
    rule_id = serializers.IntegerField(source='rule.id', read_only=True)

    class Meta:
        model = WithholdingLimit
        fields = [
            'id', 'state', 'rule_number', 'rule_id', 'wl', 'supports_2nd_family',
            'arrears_of_more_than_12_weeks', 'number_of_orders', 'weekly_de_code',
            'work_state', 'issuing_state', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rule_id', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Resolve state
        state_payload = attrs.get('rule', {}).get('state') if isinstance(attrs.get('rule'), dict) else attrs.get('state')
        state_name = None
        if isinstance(state_payload, dict):
            state_name = state_payload.get('state')
        elif isinstance(state_payload, str):
            state_name = state_payload

        if not state_name:
            raise serializers.ValidationError("state is required")

        rule_number = attrs.get('rule_number')
        if rule_number is None:
            raise serializers.ValidationError("rule_number is required")

        # Find State and corresponding WithholdingRules
        state_obj = State.objects.filter(state__iexact=state_name).first() or \
                    State.objects.filter(state_code__iexact=state_name).first()
        if not state_obj:
            raise serializers.ValidationError(f"State '{state_name}' not found")

        rule_obj = WithholdingRules.objects.filter(state=state_obj, rule=rule_number).first()
        if not rule_obj:
            raise serializers.ValidationError(
                f"WithholdingRules not found for state '{state_obj.state}' and rule_number '{rule_number}'"
            )

        # Replace incoming with resolved FK
        attrs['rule'] = rule_obj
        # Normalize state field for representation
        attrs['state'] = state_obj.state
        # Remove helper write-only
        attrs.pop('rule_number', None)
        return attrs

    def create(self, validated_data):
        return WithholdingLimit.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class PriorityDeductionSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)         
    type = serializers.CharField(source='deduction_type.type', read_only=True) 

    class Meta:
        model = DeductionPriority
        fields = [
            'priority_order',  'type', 'state'
        ]


class DeductionPriorityCRUDSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for DeductionPriority that accepts state name/code and
    deduction name instead of IDs, while storing the related IDs.
    """
    state = serializers.CharField(source='state.state')
    deduction = serializers.CharField(source='deduction_type.type')

    class Meta:
        model = DeductionPriority
        fields = [
            'id', 'state', 'deduction', 'priority_order', 'created_at', 'updated_at'
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

        # Resolve deduction by name (type field in Deductions)
        deduction_payload = attrs.get('deduction_type') or attrs.get('deduction')
        deduction_name = None
        if isinstance(deduction_payload, dict):
            deduction_name = deduction_payload.get('type') or deduction_payload.get('deduction')
        elif isinstance(deduction_payload, str):
            deduction_name = deduction_payload

        if not deduction_name:
            raise serializers.ValidationError("deduction is required")

        deduction_obj = Deductions.objects.filter(type__iexact=deduction_name).first()
        if not deduction_obj:
            raise serializers.ValidationError(f"Deduction '{deduction_name}' not found")

        # Replace nested inputs with actual model instances
        attrs['state'] = state_obj
        attrs['deduction_type'] = deduction_obj
        # Clean helper keys if present
        attrs.pop('deduction', None)
        return attrs

    def create(self, validated_data):
        return DeductionPriority.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class WithholdingRulesWithLimitsSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)
    withholding_limits = WithholdingLimitSerializer(many=True, read_only=True)
    
    class Meta:
        model = WithholdingRules
        fields = ['state', 'rule', 'allocation_method', 'withholding_limit', 'withholding_limits']

