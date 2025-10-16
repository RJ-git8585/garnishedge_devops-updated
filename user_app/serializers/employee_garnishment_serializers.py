from rest_framework import serializers
from user_app.models import EmployeeDetails, GarnishmentOrder
from processor.models import State, GarnishmentType, FedFilingStatus
from user_app.serializers.employee_serializers import StateField, FilingStatusField, ClientField


class GarnishmentTypeField(serializers.Field):
    """Custom field for handling GarnishmentType as read/write."""
    def to_representation(self, value):
        return value.type if value else None

    def to_internal_value(self, data):
        try:
            return GarnishmentType.objects.get(type__iexact=data)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError(f"Garnishment type '{data}' not found")


class GarnishmentDataSerializer(serializers.Serializer):
    """Serializer for garnishment data structure."""
    type = serializers.CharField()
    data = serializers.ListField(
        child=serializers.DictField()
    )




class EmployeeGarnishmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for complete employee garnishment details."""
    home_state = StateField()
    work_state = StateField()
    no_of_exemption_including_self = serializers.IntegerField(source='number_of_exemptions')
    filing_status = FilingStatusField()
    garnishment_data = GarnishmentDataSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeDetails
        fields = [
            "ee_id", "home_state", "work_state", "no_of_exemption_including_self",
            "filing_status", "number_of_student_default_loan", "support_second_family",
            "number_of_dependent_child", "garnishment_data"
        ]
        read_only_fields = ["ee_id", "garnishment_data"]


class EmployeeBasicUpdateSerializer(serializers.Serializer):
    """Serializer for updating basic employee data."""
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    home_state = StateField(required=False)
    work_state = StateField(required=False)
    number_of_exemptions = serializers.IntegerField(required=False)
    marital_status = serializers.CharField(max_length=255, required=False)
    number_of_student_default_loan = serializers.IntegerField(required=False)
    number_of_dependent_child = serializers.IntegerField(required=False)
    support_second_family = serializers.BooleanField(required=False)
    garnishment_fees_status = serializers.BooleanField(required=False)
    number_of_active_garnishment = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)
    
    # Add support for filing_status field
    filing_status = FilingStatusField(required=False)
    
    # Add support for garnishment order fields
    garnishment_type = GarnishmentTypeField(required=False)
    is_consumer_debt = serializers.BooleanField(required=False)
    received_date = serializers.DateField(required=False)
    start_date = serializers.DateField(required=False)
    stop_date = serializers.DateField(required=False)
    ordered_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    arrear_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    arrear_greater_than_12_weeks = serializers.BooleanField(required=False)
    
    # Add support for garnishment_data updates
    garnishment_data = GarnishmentDataSerializer(many=True, required=False)