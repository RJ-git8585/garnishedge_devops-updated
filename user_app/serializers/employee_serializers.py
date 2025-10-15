from rest_framework import serializers
from user_app.models import Client, GarnishmentOrder,EmployeeDetail
from processor.models import FedFilingStatus,State
from datetime import datetime
import re
from user_app.utils import DataProcessingUtils

class CustomDateField(serializers.DateField):
    """
    Custom date field that accepts multiple date formats and converts to YYYY-MM-DD
    Uses DataProcessingUtils for robust date parsing.
    """
    def __init__(self, **kwargs):
        # Set default values for null handling
        kwargs.setdefault('allow_null', True)
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        # Use the utility function for date parsing
        parsed_date = DataProcessingUtils.parse_date_field(data)
        
        if parsed_date is None:
            return None
        
        try:
            # Convert string back to date object for serializer
            return datetime.strptime(parsed_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                f"Date '{data}' has wrong format. Supported formats: MM-DD-YYYY, YYYY-MM-DD, MM/DD/YYYY, etc."
            )


class CustomIntegerField(serializers.IntegerField):
    """
    Custom integer field that handles string-to-integer conversions with better validation
    Uses DataProcessingUtils for robust integer parsing.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('allow_null', True)
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        # Use the utility function for integer parsing
        parsed_int = DataProcessingUtils.parse_integer_field(data)
        
        if parsed_int is None:
            return None
        
        return parsed_int


class ClientField(serializers.Field):
    """Custom field for handling Client ID as read/write."""
    def to_representation(self, value):
        return value.client_id if value else None

    def to_internal_value(self, data):
        try:
            return Client.objects.get(client_id=data)
        except Client.DoesNotExist:
            raise serializers.ValidationError(f"Client '{data}' not found")


class StateField(serializers.Field):
    """Custom field for handling State as read/write."""
    def to_representation(self, value):
        return value.state if value else None

    def to_internal_value(self, data):
        try:
            return State.objects.get(state__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError(f"State '{data}' not found")


class FilingStatusField(serializers.Field):
    """Custom field for handling Filing Status as read/write."""
    def to_representation(self, value):
        return value.name if value else None

    def to_internal_value(self, data):
        try:
            return FedFilingStatus.objects.get(name__iexact=data)
        except FedFilingStatus.DoesNotExist:
            raise serializers.ValidationError(f"Filing status '{data}' not found")


class EmployeeDetailSerializer(serializers.ModelSerializer):
    # Unified fields (same for GET and POST/PUT)
    client_id = ClientField(source='client')
    home_state = StateField()
    work_state = StateField()
    filing_status = FilingStatusField()
    
    # Custom date field that accepts multiple date formats
    garnishment_fees_suspended_till = CustomDateField()
    
    # Custom integer fields for better validation
    number_of_exemptions = CustomIntegerField()
    number_of_student_default_loan = CustomIntegerField()
    number_of_dependent_child = CustomIntegerField()
    number_of_active_garnishment = CustomIntegerField()

    class Meta:
        model = EmployeeDetail
        fields = [
            "id", "ee_id", "client_id",
            "first_name", "middle_name", "last_name",
            "ssn",
            "home_state", "work_state",
            "gender", "number_of_exemptions",
            "filing_status",
            "marital_status", "number_of_student_default_loan",
            "number_of_dependent_child", "support_second_family",
            "garnishment_fees_status", "garnishment_fees_suspended_till",
            "number_of_active_garnishment", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "record_import", "record_updated",
        ]
