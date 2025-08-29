from rest_framework import serializers
from processor.models import *
from processor.models.creditor_debt.applied_rule import CreditorDebtAppliedRule
class CreditorDebtAppliedRulesSerializers(serializers.ModelSerializer):
    class Meta:
        model = CreditorDebtAppliedRule
        fields = '__all__'


class CreditorDebtExemptAmtConfigSerializers(serializers.ModelSerializer):
    class Meta:
        model = CreditorDebtExemptAmtConfig
        fields = '__all__'

class CreditorDebtRuleSerializers(serializers.ModelSerializer):
    class Meta:
        model = CreditorDebtRule
        fields = '__all__'

class CreditorDebtRuleEditPermissionSerializers(serializers.ModelSerializer):
    class Meta:
        model = CreditorDebtRuleEditPermission
        fields = '__all__'
