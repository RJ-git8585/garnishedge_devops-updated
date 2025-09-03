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
    class Meta:
        model = StateTaxLevyExemptAmtConfig
        fields = '__all__'


class StateTaxLevyRuleEditPermissionSerializers(serializers.ModelSerializer):
    class Meta:
        model = StateTaxLevyRuleEditPermission
        fields = '__all__'