from rest_framework import serializers
from processor.models import *

class WithholdingRulesSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)
    
    class Meta:
        model = WithholdingRules
        fields = ['state', 'rule', 'allocation_method', 'withholding_limit']

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

class WithholdingRulesWithLimitsSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state', read_only=True)
    withholding_limits = WithholdingLimitSerializer(many=True, read_only=True)
    
    class Meta:
        model = WithholdingRules
        fields = ['state', 'rule', 'allocation_method', 'withholding_limit', 'withholding_limits']

