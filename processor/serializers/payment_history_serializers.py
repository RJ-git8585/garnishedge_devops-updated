"""
Serializers for Payment History API endpoints.
"""
from rest_framework import serializers
from processor.models.payment_history import PaymentHistory
from user_app.models import GarnishmentOrder, EmployeeDetail


class PaymentHistorySerializer(serializers.ModelSerializer):
    """Serializer for Payment History model."""
    ee_id = serializers.CharField(source='ee.ee_id', read_only=True)
    case_id = serializers.CharField(source='case.case_id', read_only=True)
    eft_check_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentHistory
        fields = [
            'id',
            'ee',
            'ee_id',
            'case',
            'case_id',
            'voucher_number',
            'pay_date',
            'amount_due',
            'paid_on',
            'check_number',
            'check_amount',
            'eft_check_amount',
            'ach_reference',
            'eft_check',
            'comment',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'voucher_number', 'created_at', 'updated_at']
    
    def get_eft_check_amount(self, obj):
        """Return check_amount if available, otherwise eft_check."""
        return obj.check_amount if obj.check_amount is not None else obj.eft_check


class PaymentHistorySummarySerializer(serializers.Serializer):
    """Serializer for payment history summary statistics."""
    paid_to_date = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_garnishment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    total_eft = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class PaymentHistoryListResponseSerializer(serializers.Serializer):
    """Serializer for payment history list response with summary."""
    summary = PaymentHistorySummarySerializer()
    payments = PaymentHistorySerializer(many=True)


class PaymentHistoryCreateSerializer(serializers.Serializer):
    """Serializer for creating payment history records."""
    ee_id = serializers.CharField(required=True, help_text="Employee ID (ee_id)")
    case_id = serializers.CharField(required=True, help_text="Garnishment order case_id")
    pay_date = serializers.DateField(required=True)
    amount_due = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True
    )
    check_number = serializers.CharField(
        max_length=50, 
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    check_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        allow_null=True
    )
    comment = serializers.CharField(
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    paid_on = serializers.DateField(required=False, allow_null=True)
    ach_reference = serializers.CharField(
        max_length=255, 
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    
    def validate_ee_id(self, value):
        """Validate that the employee exists."""
        if not EmployeeDetail.objects.filter(ee_id=value).exists():
            raise serializers.ValidationError(f"Employee with ee_id '{value}' does not exist.")
        return value
    
    def validate_case_id(self, value):
        """Validate that the case_id exists."""
        if not GarnishmentOrder.objects.filter(case_id=value).exists():
            raise serializers.ValidationError(f"Garnishment order with case_id '{value}' does not exist.")
        return value

