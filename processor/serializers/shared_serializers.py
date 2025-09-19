from rest_framework import serializers
from processor.models import MultipleGarnPriorityOrders,ThresholdCondition,ExemptConfig,ThresholdAmount,PayPeriod, State, GarnishmentType, ExemptRule


class PayPeriodSerializers(serializers.ModelSerializer):

    class Meta:
        model = PayPeriod
        fields = [ 'state_code', 'state']

class StateSerializer(serializers.ModelSerializer):
    class Meta :
        model = State
        fields = '__all__'

class GarnishmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarnishmentType
        fields = '__all__'

class ExemptConfigSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)         
    pay_period = serializers.CharField(source='pay_period.name', read_only=True) 

    class Meta:
        model = ExemptConfig
        fields = [
            'debt_type', 'is_filing_status', 'wage_basis',
            'wage_amount', 'percent_limit', 'state', 'pay_period'
        ]


class ThresholdAmountSerializer(serializers.ModelSerializer):
    debt_type = serializers.CharField(source='config.debt_type', read_only=True)
    ftb_type = serializers.CharField(source='config.ftb_type', read_only=True)
    is_filing_status = serializers.BooleanField(source='config.is_filing_status', read_only=True)
    wage_amount = serializers.FloatField(source='config.wage_amount', read_only=True)
    percent_limit = serializers.IntegerField(source='config.percent_limit', allow_null=True, read_only=True)
    state = serializers.CharField(source='config.state.state', read_only=True)
    pay_period = serializers.CharField(source='config.pay_period.name', read_only=True)
    start_gt_5dec24= serializers.BooleanField(source='config.start_gt_5dec24', read_only=True)

    class Meta:
        model = ThresholdAmount
        fields = [
            'id','ftb_type',
            'debt_type', 'is_filing_status', 'wage_amount', 'percent_limit',
            'state', 'pay_period', 'lower_threshold_amount', 'lower_threshold_percent1', 'lower_threshold_percent2',
            'mid_threshold_amount', 'mid_threshold_percent',
            'upper_threshold_amount', 'upper_threshold_percent',
            'de_range_lower_to_upper_threshold_percent',
            'de_range_lower_to_mid_threshold_percent',
            'de_range_mid_to_upper_threshold_percent',
            'filing_status_percent','start_gt_5dec24','exempt_amt',
        ]


class MultipleGarnPriorityOrderCRUDSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for MultipleGarnPriorityOrders that accepts state name/code and
    garnishment type name instead of IDs, while storing the related IDs.
    """
    state = serializers.CharField(source='state.state')
    garnishment = serializers.CharField(source='garnishment_type.type')

    class Meta:
        model = MultipleGarnPriorityOrders
        fields = [
            'id', 'state', 'garnishment', 'priority_order', 'created_at', 'updated_at'
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


class ThresholdAmountCoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThresholdAmount
        exclude = ("config",)  
    

class ExemptConfigWithThresholdSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="state.state")  
    pay_period = serializers.CharField(source="pay_period.name")
    garnishment_type = serializers.CharField(source="garnishment_type.type")
    threshold_amounts = ThresholdAmountCoreSerializer(many=True, required=False)

    class Meta:
        model = ExemptConfig
        fields = [
            "id", "debt_type", "is_filing_status", "wage_basis",
            "wage_amount", "percent_limit", "state", "pay_period", "garnishment_type",
            "start_gt_5dec24", "threshold_amounts"
        ]

    def create(self, validated_data):
        threshold_data = validated_data.pop("threshold_amounts", [])
        config = ExemptConfig.objects.create(**validated_data)
        for t in threshold_data:
            ThresholdAmount.objects.create(config=config, **t)
        return config

    def update(self, instance, validated_data):
        threshold_data = validated_data.pop("threshold_amounts", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update thresholds → simple approach: delete and recreate
        if threshold_data:
            instance.thresholdamount_set.all().delete()
            for t in threshold_data:
                ThresholdAmount.objects.create(config=instance, **t)
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["threshold_amounts"] = ThresholdAmountSerializer(
            instance.thresholdamount_set.all(), many=True
        ).data
        return rep


class BaseGarnishmentTypeExemptConfigSerializer(serializers.ModelSerializer):
    """
    Base serializer for garnishment type specific ExemptConfig operations.
    This class provides common functionality for all garnishment type specific serializers.
    """
    state = serializers.CharField(source="state.state")  
    pay_period = serializers.CharField(source="pay_period.name")
    garnishment_type = serializers.CharField(source="garnishment_type.type", read_only=True)
    rule_id = serializers.IntegerField(source="rule.id", read_only=True)
    threshold_amounts = ThresholdAmountCoreSerializer(many=True, required=False)

    class Meta:
        model = ExemptConfig
        fields = [
            "id", "rule_id", "debt_type", "is_filing_status", "wage_basis",
            "wage_amount", "percent_limit", "state", "pay_period", "garnishment_type",
            "start_gt_5dec24", "threshold_amounts"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'garnishment_type_name'):
            raise NotImplementedError("Subclasses must define garnishment_type_name")

    def validate(self, data):
        """
        Validate that we're only working with the specific garnishment type
        """
        # Get the state and pay_period objects
        state_obj = data.get('state')
        pay_period_obj = data.get('pay_period')
        
        if state_obj and pay_period_obj:
            # Check if there's already a config for this garnishment type, state/pay_period
            existing_config = ExemptConfig.objects.filter(
                state=state_obj,
                pay_period=pay_period_obj,
                garnishment_type__type=self.garnishment_type_name
            ).first()
            
            # If updating, make sure the instance is the correct garnishment type
            if self.instance and self.instance.garnishment_type.type != self.garnishment_type_name:
                raise serializers.ValidationError(
                    f"This serializer only works with {self.garnishment_type_name} garnishment type"
                )
        
        return data

    def create(self, validated_data):
        """
        Create ExemptConfig specifically for the garnishment type
        """
        threshold_data = validated_data.pop("threshold_amounts", [])
        
        # Get or create the garnishment type
        garnishment_type_obj, created = GarnishmentType.objects.get_or_create(
            type=self.garnishment_type_name,
            defaults={'description': f'{self.garnishment_type_name} Garnishment'}
        )
        
        # Set the garnishment_type
        validated_data['garnishment_type'] = garnishment_type_obj
        
        config = ExemptConfig.objects.create(**validated_data)
        
        # Create threshold amounts
        for t in threshold_data:
            ThresholdAmount.objects.create(config=config, **t)
        
        return config

    def update(self, instance, validated_data):
        """
        Update ExemptConfig ensuring it remains the correct garnishment type
        """
        # Ensure we're only updating records of the correct garnishment type
        if instance.garnishment_type.type != self.garnishment_type_name:
            raise serializers.ValidationError(
                f"This serializer only works with {self.garnishment_type_name} garnishment type"
            )
        
        threshold_data = validated_data.pop("threshold_amounts", [])
        
        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update thresholds → simple approach: delete and recreate
        if threshold_data:
            instance.thresholdamount_set.all().delete()
            for t in threshold_data:
                ThresholdAmount.objects.create(config=instance, **t)
        
        return instance

    def to_representation(self, instance):
        """
        Custom representation to ensure only the correct garnishment type data is returned
        """
        # Filter to only show records of the correct garnishment type
        if instance.garnishment_type.type != self.garnishment_type_name:
            return None
            
        rep = super().to_representation(instance)
        rep["threshold_amounts"] = ThresholdAmountSerializer(
            instance.thresholdamount_set.all(), many=True
        ).data
        return rep


class CreditorDebtExemptConfigSerializer(BaseGarnishmentTypeExemptConfigSerializer):
    """
    Serializer specifically for Creditor_Debt garnishment type.
    - Automatically filters and works only with Creditor_Debt garnishment type
    - Prevents creation/update of other garnishment types
    """
    garnishment_type_name = "Creditor_Debt"


class StateTaxLevyExemptConfigSerializer(BaseGarnishmentTypeExemptConfigSerializer):
    """
    Serializer specifically for State_Tax_Levy garnishment type.
    - Automatically filters and works only with State_Tax_Levy garnishment type
    - Prevents creation/update of other garnishment types
    """
    garnishment_type_name = "State_Tax_Levy"


def get_garnishment_type_serializer(garnishment_type):
    """
    Factory function to return the appropriate serializer based on garnishment type.
    
    Args:
        garnishment_type (str): The garnishment type (e.g., 'creditor_debt', 'state_tax_levy')
    
    Returns:
        Serializer class: The appropriate serializer for the garnishment type
    
    Raises:
        ValueError: If garnishment_type is not supported
    """
    serializer_mapping = {
        'creditor_debt': CreditorDebtExemptConfigSerializer,
        'state_tax_levy': StateTaxLevyExemptConfigSerializer,
    }
    
    # Normalize the input (convert to lowercase and handle variations)
    normalized_type = garnishment_type.lower().replace('_', '_')
    
    # Try exact match first, then lowercase match
    serializer_class = serializer_mapping.get(garnishment_type) or serializer_mapping.get(normalized_type)
    
    if not serializer_class:
        supported_types = list(serializer_mapping.keys())
        raise ValueError(f"Unsupported garnishment type: {garnishment_type}. Supported types: {supported_types}")
    
    return serializer_class


class ThresholdConditionSerializer(serializers.ModelSerializer):
    """
    Serializer for ThresholdCondition.
    - Allows write with `threshold_id`.
    - Returns nested threshold details in GET.
    """
    # Write-only field for foreign key
    threshold_id = serializers.PrimaryKeyRelatedField(
        queryset=ThresholdAmount.objects.all(),
        source="threshold",
        write_only=True
    )

    # Read-only nested threshold details
    threshold = ThresholdAmountSerializer(read_only=True)

    class Meta:
        model = ThresholdCondition
        fields = [
            "id",
            "threshold_id",  
            "threshold",     
            "multiplier_lt",
            "condition_expression_lt",
            "multiplier_mid",
            "condition_expression_mid",
            "multiplier_ut",
            "condition_expression_ut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BaseGarnishmentTypeExemptRuleSerializer(serializers.ModelSerializer):
    """
    Base serializer for garnishment type specific ExemptRule operations.
    This class provides common functionality for all garnishment type specific serializers.
    """
    state = serializers.CharField(source="state.state")  
    garnishment_type = serializers.CharField(source="garnishment_type.type", read_only=True)

    class Meta:
        model = ExemptRule
        fields = [
            "id", "state", "garnishment_type", "deduction_basis",
            "withholding_limit", "rule", "created_at", "updated_at"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'garnishment_type_name'):
            raise NotImplementedError("Subclasses must define garnishment_type_name")

    def validate(self, data):
        """
        Validate that we're only working with the specific garnishment type
        """
        # Get the state object
        state_obj = data.get('state')
        
        if state_obj:
            # Check if there's already a rule for this garnishment type, state
            existing_rule = ExemptRule.objects.filter(
                state=state_obj,
                garnishment_type__type=self.garnishment_type_name
            ).first()
            
            # If updating, make sure the instance is the correct garnishment type
            if self.instance and self.instance.garnishment_type.type != self.garnishment_type_name:
                raise serializers.ValidationError(
                    f"This serializer only works with {self.garnishment_type_name} garnishment type"
                )
        
        return data

    def create(self, validated_data):
        """
        Create ExemptRule specifically for the garnishment type
        """
        # Get or create the garnishment type
        garnishment_type_obj, created = GarnishmentType.objects.get_or_create(
            type=self.garnishment_type_name,
            defaults={'description': f'{self.garnishment_type_name} Garnishment'}
        )
        
        # Set the garnishment_type
        validated_data['garnishment_type'] = garnishment_type_obj
        
        rule = ExemptRule.objects.create(**validated_data)
        return rule

    def update(self, instance, validated_data):
        """
        Update ExemptRule ensuring it remains the correct garnishment type
        """
        # Ensure we're only updating records of the correct garnishment type
        if instance.garnishment_type.type != self.garnishment_type_name:
            raise serializers.ValidationError(
                f"This serializer only works with {self.garnishment_type_name} garnishment type"
            )
        
        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance

    def to_representation(self, instance):
        """
        Custom representation to ensure only the correct garnishment type data is returned
        """
        # Filter to only show records of the correct garnishment type
        if instance.garnishment_type.type != self.garnishment_type_name:
            return None
            
        return super().to_representation(instance)


class CreditorDebtExemptRuleSerializer(BaseGarnishmentTypeExemptRuleSerializer):
    """
    Serializer specifically for Creditor_Debt garnishment type.
    - Automatically filters and works only with Creditor_Debt garnishment type
    - Prevents creation/update of other garnishment types
    """
    garnishment_type_name = "Creditor_Debt"


class StateTaxLevyExemptRuleSerializer(BaseGarnishmentTypeExemptRuleSerializer):
    """
    Serializer specifically for State_Tax_Levy garnishment type.
    - Automatically filters and works only with State_Tax_Levy garnishment type
    - Prevents creation/update of other garnishment types
    """
    garnishment_type_name = "State_Tax_Levy"


def get_garnishment_type_rule_serializer(garnishment_type):
    """
    Factory function to return the appropriate ExemptRule serializer based on garnishment type.
    
    Args:
        garnishment_type (str): The garnishment type (e.g., 'creditor_debt', 'state_tax_levy')
    
    Returns:
        Serializer class: The appropriate serializer for the garnishment type
    
    Raises:
        ValueError: If garnishment_type is not supported
    """
    serializer_mapping = {
        'creditor_debt': CreditorDebtExemptRuleSerializer,
        'state_tax_levy': StateTaxLevyExemptRuleSerializer,
    }
    
    # Normalize the input (convert to lowercase and handle variations)
    normalized_type = garnishment_type.lower().replace('_', '_')
    
    # Try exact match first, then lowercase match
    serializer_class = serializer_mapping.get(garnishment_type) or serializer_mapping.get(normalized_type)
    
    if not serializer_class:
        supported_types = list(serializer_mapping.keys())
        raise ValueError(f"Unsupported garnishment type: {garnishment_type}. Supported types: {supported_types}")
    
    return serializer_class
