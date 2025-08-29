from rest_framework import serializers
from processor.models import PriorityOrders,ThresholdCondition,ExemptConfig,ThresholdAmount,PayPeriod, State, GarnishmentType


class PayPeriodSerializers(serializers.ModelSerializer):

    class Meta:
        model = PayPeriod
        fields = '__all__'

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
    is_filing_status = serializers.BooleanField(source='config.is_filing_status', read_only=True)
    wage_amount = serializers.FloatField(source='config.wage_amount', read_only=True)
    percent_limit = serializers.IntegerField(source='config.percent_limit', allow_null=True, read_only=True)
    state = serializers.CharField(source='config.state.state', read_only=True)
    pay_period = serializers.CharField(source='config.pay_period.name', read_only=True)
    start_gt_5dec24= serializers.BooleanField(source='config.start_gt_5dec24', read_only=True)

    class Meta:
        model = ThresholdAmount
        fields = [
            'id',
            'debt_type', 'is_filing_status', 'wage_amount', 'percent_limit',
            'state', 'pay_period', 'lower_threshold_amount', 'lower_threshold_percent1', 'lower_threshold_percent2',
            'mid_threshold_amount', 'mid_threshold_percent',
            'upper_threshold_amount', 'upper_threshold_percent',
            'de_range_lower_to_upper_threshold_percent',
            'de_range_lower_to_mid_threshold_percent',
            'de_range_mid_to_upper_threshold_percent',
            'filing_status_percent','start_gt_5dec24','exempt_amt'
        ]

class PriorityOrderSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)         
    type = serializers.CharField(source='garnishment_type.type', read_only=True) 

    class Meta:
        model = PriorityOrders
        fields = [
            'priority_order',  'type', 'state'
        ]


class ThresholdAmountCoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThresholdAmount
        exclude = ("config",)  # config will come from ExemptConfig
    

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


class ThresholdAmountSerializer(serializers.ModelSerializer):
    """Minimal serializer for ThresholdAmount (used for nested response)."""
    class Meta:
        model = ThresholdAmount
        fields = ["id", "amount"]  # adjust fields of ThresholdAmount as per your model


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
            "threshold_id",  # for POST/PUT
            "threshold",     # for GET
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
