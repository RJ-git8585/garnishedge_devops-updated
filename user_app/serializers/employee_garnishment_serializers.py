from rest_framework import serializers
from user_app.models import EmployeeDetail, GarnishmentOrder
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
        model = EmployeeDetail
        fields = [
            "ee_id", "home_state", "work_state", "no_of_exemption_including_self",
            "filing_status", "age", "is_blind", "is_spouse_blind",
            "spouse_age", "no_of_student_default_loan", "statement_of_exemption_received_date",
            "garn_start_date", "support_second_family", "arrears_greater_than_12_weeks",
            "no_of_dependent_child", "consumer_debt", "non_consumer_debt", "garnishment_data"
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
