from rest_framework import serializers
from user_app.models import Client, GarnishmentOrder,EmployeeDetail
from processor.models import FedFilingStatus,State
from datetime import datetime

class CustomDateField(serializers.DateField):
    """
    Custom date field that accepts MM-DD-YYYY format and converts to YYYY-MM-DD
    """
    def __init__(self, **kwargs):
        # Set default values for null handling
        kwargs.setdefault('allow_null', True)
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        # Handle null/empty values
        if data is None or data == '' or data == 'null':
            return None
        
        try:
            # Try to parse MM-DD-YYYY format
            if isinstance(data, str) and len(data.split('-')) == 3:
                parts = data.split('-')
                if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                    # MM-DD-YYYY format
                    month, day, year = parts
                    date_obj = datetime.strptime(f"{month}-{day}-{year}", "%m-%d-%Y")
                    return date_obj.date()
            
            # If not MM-DD-YYYY format, try default parsing
            return super().to_internal_value(data)
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                "Date has wrong format. Use MM-DD-YYYY format (e.g., 01-20-2024)."
            )


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
    
    # Custom date field that accepts MM-DD-YYYY format
    garnishment_fees_suspended_till = CustomDateField()

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
