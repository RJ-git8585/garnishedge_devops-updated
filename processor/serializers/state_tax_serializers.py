from rest_framework import serializers
from processor.models.state_tax_levy import StateTaxLevyExemptAmtConfig,StateTaxLevyAppliedRule,StateTaxLevyConfig,StateTaxLevyRuleEditPermission
class StateTaxLevyConfigSerializers(serializers.ModelSerializer):
    class Meta:
        model = StateTaxLevyConfig
        fields = '__all__'

class StateTaxLevyRulesSerializers(serializers.ModelSerializer):
    class Meta:
        model = StateTaxLevyAppliedRule
        exclude = ['id']




class StateTaxLevyExemptAmtConfigSerializers(serializers.ModelSerializer):
    state = serializers.CharField(source='state.state')
    pay_period = serializers.CharField(source='pay_period.name')
    class Meta:
        model = StateTaxLevyExemptAmtConfig
        fields = ['state','pay_period','minimum_hourly_wage_basis','minimum_wage_amount','multiplier_lt','condition_expression_lt','lower_threshold_amount','multiplier_ut','condition_expression_ut','upper_threshold_amount']



class StateTaxLevyRuleEditPermissionSerializers(serializers.ModelSerializer):
    class Meta:
        model = StateTaxLevyRuleEditPermission
        fields = '__all__'