from rest_framework import serializers
from user_app.models import EmployeeDetail, GarnishmentOrder
from processor.models import State, GarnishmentType, FedFilingStatus


class PayrollTaxesSerializer(serializers.Serializer):
    """Serializer for payroll taxes data"""
    federal_income_tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    state_tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    local_other_taxes = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    medicare_tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    social_security_tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    wilmington_tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    california_sdi = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    medical_insurance_pretax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    life_insurance = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    retirement_401k = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    industrial_insurance = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    union_dues = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)


class GarnishmentDataSerializer(serializers.Serializer):
    """Serializer for individual garnishment data"""
    case_id = serializers.CharField()
    ordered_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    arrear_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)


class GarnishmentTypeDataSerializer(serializers.Serializer):
    """Serializer for garnishment type with its data"""
    type = serializers.CharField()
    data = GarnishmentDataSerializer(many=True)


class BatchCaseInputSerializer(serializers.Serializer):
    """Serializer for individual case in batch input"""
    client_id = serializers.CharField()
    ee_id = serializers.CharField()
    pay_period = serializers.CharField()
    payroll_date = serializers.DateField()
    wages = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission_and_bonus = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    non_accountable_allowances = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    gross_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    payroll_taxes = PayrollTaxesSerializer()
    net_pay = serializers.DecimalField(max_digits=12, decimal_places=2)


class BatchInputSerializer(serializers.Serializer):
    """Serializer for batch input"""
    batch_id = serializers.CharField()
    cases = BatchCaseInputSerializer(many=True)


class BatchCaseOutputSerializer(serializers.Serializer):
    """Serializer for enriched case output"""
    client_id = serializers.CharField(required=False)
    ee_id = serializers.CharField()
    work_state = serializers.CharField(required=False)
    home_state = serializers.CharField(required=False)
    issuing_state = serializers.CharField(required=False)
    no_of_exemption_including_self = serializers.IntegerField(required=False)
    is_multiple_garnishment_type = serializers.BooleanField(required=False)
    no_of_student_default_loan = serializers.IntegerField(required=False)
    pay_period = serializers.CharField()
    filing_status = serializers.CharField(required=False)
    wages = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission_and_bonus = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    non_accountable_allowances = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    gross_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    payroll_taxes = PayrollTaxesSerializer()
    net_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_blind = serializers.BooleanField(required=False)
    statement_of_exemption_received_date = serializers.CharField(required=False)
    garn_start_date = serializers.CharField(required=False)
    non_consumer_debt = serializers.BooleanField(required=False)
    consumer_debt = serializers.BooleanField(required=False)
    age = serializers.IntegerField(required=False)
    spouse_age = serializers.IntegerField(required=False)
    is_spouse_blind = serializers.BooleanField(required=False)
    support_second_family = serializers.BooleanField(required=False)
    no_of_dependent_child = serializers.IntegerField(required=False)
    arrear_greater_than_12_weeks = serializers.BooleanField(required=False)
    ftb_type = serializers.CharField(required=False, allow_null=True)
    garnishment_data = GarnishmentTypeDataSerializer(many=True, required=False)
    garnishment_orders = serializers.ListField(child=serializers.CharField(), required=False)


class BatchOutputSerializer(serializers.Serializer):
    """Serializer for batch output"""
    batch_id = serializers.CharField()
    cases = BatchCaseOutputSerializer(many=True)


class EmployeeNotFoundSerializer(serializers.Serializer):
    """Serializer for employee not found response"""
    not_found = serializers.CharField()
    message = serializers.CharField()
