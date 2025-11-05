from rest_framework import serializers
from processor.models import MultipleGarnPriorityOrders,ThresholdCondition,ExemptConfig,ThresholdAmount,PayPeriod, State, GarnishmentType, ExemptRule
from user_app.utils import DataProcessingUtils
from datetime import datetime


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



class StateField(serializers.Field):
    """Custom field for handling State as read/write."""
    def to_representation(self, value):
        return value.state if value else None

    def to_internal_value(self, data):
        if data is None or data == '':
            return None
        try:
            return State.objects.get(state__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError(f"State '{data}' not found")


class PayPeriodField(serializers.Field):
    """Custom field for handling PayPeriod as read/write."""
    def to_representation(self, value):
        return value.name if value else None

    def to_internal_value(self, data):
        if data is None or data == '':
            return None
        try:
            return PayPeriod.objects.get(name__iexact=data)
        except PayPeriod.DoesNotExist:
            raise serializers.ValidationError(f"PayPeriod '{data}' not found")


class GarnishmentTypeField(serializers.Field):
    """Custom field for handling GarnishmentType as read/write."""
    def to_representation(self, value):
        return value.type if value else None

    def to_internal_value(self, data):
        if data is None or data == '':
            return None
        try:
            return GarnishmentType.objects.get(type__iexact=data)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError(f"GarnishmentType '{data}' not found")


class RuleField(serializers.Field):
    """Custom field for handling ExemptRule as read/write using rule_id."""
    def to_representation(self, value):
        return value.id if value else None

    def to_internal_value(self, data):
        if data is None or data == '':
            raise serializers.ValidationError("rule_id is required")
        try:
            # Accept both integer ID or ExemptRule object
            if isinstance(data, int):
                return ExemptRule.objects.get(id=data)
            elif hasattr(data, 'id'):
                return data
            else:
                raise serializers.ValidationError(f"Invalid rule_id: {data}")
        except ExemptRule.DoesNotExist:
            raise serializers.ValidationError(f"ExemptRule with id '{data}' not found")


class FlexibleDateField(serializers.DateField):
    """Custom date field that uses parse_date_field to handle various date formats."""
    def to_internal_value(self, data):
        """
        Parse date using the flexible parse_date_field utility.
        Accepts various date formats and converts them to YYYY-MM-DD.
        """
        if data is None or data == '':
            raise serializers.ValidationError("This field is required.")
        
        # Use the parse_date_field utility to handle various formats
        parsed_date_str = DataProcessingUtils.parse_date_field(data)
        
        if parsed_date_str is None:
            raise serializers.ValidationError(
                f"Date has wrong format. Use one of these formats instead: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, etc."
            )
        
        # Parse the YYYY-MM-DD string to a date object
        try:
            return datetime.strptime(parsed_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                f"Date has wrong format. Use one of these formats instead: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, etc."
            )





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
    home_state = serializers.CharField(source='config.home_state', read_only=True)
    percent_limit = serializers.IntegerField(source='config.percent_limit', allow_null=True, read_only=True)
    state = serializers.CharField(source='config.state.state', read_only=True)
    pay_period = serializers.CharField(source='config.pay_period.name', read_only=True)
    garn_start_date= serializers.DateField(source='config.garn_start_date', read_only=True)

    class Meta:
        model = ThresholdAmount
        fields = [
            'id','ftb_type',
            'debt_type', 'is_filing_status', 'wage_amount', 'percent_limit',
            'state', 'pay_period', 'lower_threshold_amount', 'lower_threshold_percent1', 'lower_threshold_percent2',
            'mid_threshold_amount', 'mid_threshold_percent',
            'upper_threshold_amount', 'upper_threshold_percent',
            'gp_lower_threshold_amount', 'gp_lower_threshold_percent1',
            'de_range_lower_to_upper_threshold_percent',
            'de_range_lower_to_mid_threshold_percent',
            'de_range_mid_to_upper_threshold_percent',
            'filing_status_percent','garn_start_date','exempt_amt','home_state'
        ]



class ThresholdAmountCoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThresholdAmount
        exclude = ("config",)  
    

class ExemptConfigWithThresholdSerializer(serializers.ModelSerializer):
    state = StateField(required=False, allow_null=True)
    pay_period = PayPeriodField(required=False, allow_null=True)
    garnishment_type = GarnishmentTypeField(required=False, allow_null=True)
    threshold_amounts = ThresholdAmountCoreSerializer(many=True, required=False)

    class Meta:
        model = ExemptConfig
        fields = [
            "id", "debt_type", "is_filing_status", "wage_basis",
            "wage_amount", "percent_limit", "state", "pay_period", "garnishment_type",
            "garn_start_date", "threshold_amounts","home_state"
        ]

    def create(self, validated_data):
        threshold_data = validated_data.pop("threshold_amounts", [])
        config = ExemptConfig.objects.create(**validated_data)
        for t in threshold_data:
            ThresholdAmount.objects.create(config=config, **t)
        return config

    def update(self, instance, validated_data):
        print("Validated data in update:", validated_data)

        threshold_data = validated_data.pop("threshold_amounts", [])

        #  Update parent
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        #  Convert incoming list → dict by id
        incoming_by_id = {
            item["id"]: item for item in threshold_data if item.get("id") is not None
        }

        #  Current children
        existing_qs = instance.thresholds.all()
        existing_by_id = {obj.id: obj for obj in existing_qs}

        #  1) UPDATE
        for threshold_id, existing_obj in existing_by_id.items():
            if threshold_id in incoming_by_id:
                payload = incoming_by_id[threshold_id]
                for attr, value in payload.items():
                    if attr != "id":
                        setattr(existing_obj, attr, value)
                existing_obj.save()

        #  2) CREATE
        for item in threshold_data:
            if not item.get("id"):
                item.pop("id", None)
                instance.thresholds.create(**item)

        #  3) DELETE missing
        incoming_ids = {item.get("id") for item in threshold_data if item.get("id")}
        ids_to_delete = set(existing_by_id.keys()) - incoming_ids

        if ids_to_delete:
            instance.thresholds.filter(id__in=ids_to_delete).delete()

        return instance


class BaseGarnishmentTypeExemptConfigSerializer(serializers.ModelSerializer):
    """
    Base serializer for garnishment type specific ExemptConfig operations.
    This class provides common functionality for all garnishment type specific serializers.
    """
    state = StateField(required=False, allow_null=True)
    pay_period = PayPeriodField(required=False, allow_null=True)
    garnishment_type = serializers.CharField(source="garnishment_type.type", read_only=True)
    rule_id = RuleField(source="rule", required=True)
    effective_date = FlexibleDateField(required=True)
    threshold_amounts = ThresholdAmountCoreSerializer(many=True, required=False)

    class Meta:
        model = ExemptConfig
        fields = [
            "id", "rule_id", "debt_type", "is_filing_status", "wage_basis",
            "wage_amount", "percent_limit", "state", "pay_period", "garnishment_type",
            "garn_start_date", "threshold_amounts", "home_state", "is_active", "effective_date"
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'garnishment_type_name'):
            raise NotImplementedError("Subclasses must define garnishment_type_name")

    def validate(self, data):
        """
        Validate that we're only working with the specific garnishment type
        """
        # Validate rule belongs to the correct garnishment type
        rule_obj = data.get('rule')
        if rule_obj:
            if rule_obj.garnishment_type.type != self.garnishment_type_name:
                raise serializers.ValidationError(
                    f"Rule must belong to {self.garnishment_type_name} garnishment type, "
                    f"but it belongs to {rule_obj.garnishment_type.type}"
                )
        
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
        
        # Remove id from validated_data if present (should not set ID when creating)
        validated_data.pop("id", None)
        
        # Get or create the garnishment type
        garnishment_type_obj, created = GarnishmentType.objects.get_or_create(
            type=self.garnishment_type_name,
            defaults={'description': f'{self.garnishment_type_name} Garnishment'}
        )
        
        # Set the garnishment_type
        validated_data['garnishment_type'] = garnishment_type_obj
        
        config = ExemptConfig.objects.create(**validated_data)
        
        # Create threshold amounts - remove IDs for new records
        for t in threshold_data:
            # Remove id from threshold data when creating new threshold amounts
            t.pop("id", None)
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


class BaseGarnishmentTypeExemptRuleSerializer(serializers.ModelSerializer):
    """
    Base serializer for garnishment type specific ExemptRule operations.
    This class provides common functionality for all garnishment type specific serializers.
    """
    state = StateField()
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

