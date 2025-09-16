from rest_framework import serializers
from processor.models.garnishment_fees import (GarnishmentFees,
                                                    GarnishmentFeesRules)
from processor.models import GarnishmentFees, PayPeriod, GarnishmentFeesRules
from processor.models import State, GarnishmentType


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
    # Show readable values instead of IDs
    state = serializers.CharField(source="state.state", read_only=True)
    garnishment_type = serializers.CharField(source="garnishment_type.type", read_only=True)
    pay_period = serializers.CharField(source="pay_period.name", read_only=True)
    rule = serializers.CharField(source="rule.rule", read_only=True)

    class Meta:
        model = GarnishmentFees
        fields = [
            "id",
            "state",
            "garnishment_type",
            "pay_period",
            "rule",
            "amount",
            "status",
            "payable_by",
            "created_at",
            "updated_at",
        ]




# ---------- Custom Field Types ----------

class StateField(serializers.Field):
    def to_representation(self, value: State):
        return value.state if value else None

    def to_internal_value(self, data):
        try:
            return State.objects.get(state__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"State '{data}' not found"})


class PayPeriodField(serializers.Field):
    def to_representation(self, value: PayPeriod):
        return value.name if value else None

    def to_internal_value(self, data):
        try:
            return PayPeriod.objects.get(name__iexact=data)
        except PayPeriod.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"PayPeriod '{data}' not found"})


class GarnishmentTypeField(serializers.Field):
    def to_representation(self, value: GarnishmentType):
        return value.type if value else None

    def to_internal_value(self, data):
        try:
            return GarnishmentType.objects.get(type__iexact=data)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"GarnishmentType '{data}' not found"})


class GarnishmentRuleField(serializers.Field):
    def to_representation(self, value: GarnishmentFeesRules):
        return value.rule if value else None

    def to_internal_value(self, data):
        try:
            return GarnishmentFeesRules.objects.get(rule__iexact=data)
        except GarnishmentFeesRules.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"Rule '{data}' not found"})


# ---------- Serializer ----------

class GarnishmentFeesSerializer(serializers.ModelSerializer):
    """
    Serializer for GarnishmentFees model.
    - GET: returns human-readable names for related fields.
    - POST/PUT: accepts natural keys (strings) instead of IDs.
    """

    state = StateField()
    garnishment_type = GarnishmentTypeField()
    pay_period = PayPeriodField()
    rule = GarnishmentRuleField()

    class Meta:
        model = GarnishmentFees
        fields = [
            "id",
            "state",
            "garnishment_type",
            "pay_period",
            "rule",
            "amount",
            "status",
            "payable_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")
