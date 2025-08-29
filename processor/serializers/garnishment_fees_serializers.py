from rest_framework import serializers
from processor.models.garnishment_fees import (GarnishmentFees,
                                                    GarnishmentFeesRules)

class GarnishmentFeesRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarnishmentFeesRules
        fields = '__all__'

class GarnishmentFeesRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarnishmentFeesRules
        fields = ['id', 'rule', 'maximum_fee_deduction',
                  'per_pay_period', 'per_month', 'per_remittance']

class GarnishmentFeesSerializer(serializers.ModelSerializer):
    rule = GarnishmentFeesRulesSerializer() 

    class Meta:
        model = GarnishmentFees
        fields = '__all__'

class GarnishmentFeesFlatSerializer(serializers.ModelSerializer):
    # Merge GarnishmentFeesRules fields into this serializer
    rule = serializers.CharField(source='rule.rule')
    maximum_fee_deduction = serializers.CharField(source='rule.maximum_fee_deduction')
    per_pay_period = serializers.DecimalField(source='rule.per_pay_period', max_digits=12, decimal_places=2)
    per_month = serializers.DecimalField(source='rule.per_month', max_digits=12, decimal_places=2)
    per_remittance = serializers.DecimalField(source='rule.per_remittance', max_digits=12, decimal_places=2)
    rule_created_at = serializers.DateTimeField(source='rule.created_at')
    rule_updated_at = serializers.DateTimeField(source='rule.updated_at')

    class Meta:
        model = GarnishmentFees
        fields = [
            "id",
            "state",
            "garnishment_type",
            "pay_period",
            "amount",
            "status",
            "rule",  # Rule name
            "maximum_fee_deduction",
            "per_pay_period",
            "per_month",
            "per_remittance",
            "rule_created_at",
            "rule_updated_at",
            "payable_by",
        ]
