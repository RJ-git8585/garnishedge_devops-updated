from rest_framework import serializers
from user_app.models import Client, GarnishmentOrder,EmployeeDetail, EmplopyeeAddress
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

class EmployeeAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for EmployeeAddress nested within EmployeeDetailsSerializer.
    """
    
    class Meta:
        model = EmplopyeeAddress
        fields = ['address_1', 'address_2', 'zip_code', 'geo_code', 'city', 'state', 'county', 'country']



class EmployeeDetailsSerializer(serializers.ModelSerializer):
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
    address= EmployeeAddressSerializer(required=False, allow_null=True)

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
            "number_of_active_garnishment", "status",
            "created_at", "updated_at","address"
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "record_import", "record_updated",
        ]

    def create(self, validated_data):
        """
        Create EmployeeDetail and associated EmployeeAddress.
        """
        address_data = validated_data.pop('address', None)
        employee = EmployeeDetail.objects.create(**validated_data)
        
        if address_data:
            EmplopyeeAddress.objects.create(ee=employee, **address_data)
        
        return employee

    def update(self, instance, validated_data):
        """
        Update EmployeeDetail and associated EmployeeAddress.
        """
        address_data = validated_data.pop('address', None)
        
        # Update EmployeeDetail fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update or create EmployeeAddress
        if address_data is not None:
            address_instance, created = EmplopyeeAddress.objects.get_or_create(
                ee=instance,
                defaults=address_data
            )
            if not created:
                for attr, value in address_data.items():
                    setattr(address_instance, attr, value)
                address_instance.save()
        
        return instance

    def to_representation(self, instance):
        """
        Custom representation to include nested address data.
        """
        representation = super().to_representation(instance)
        
        # Include address data if it exists
        # For OneToOneField with related_name='employee_addresses', access it via that name
        # OneToOneField raises RelatedObjectDoesNotExist (subclass of AttributeError) when related object doesn't exist
        try:
            address = instance.employee_addresses
            representation['address'] = EmployeeAddressSerializer(address).data
        except AttributeError:
            # Related object doesn't exist
            representation['address'] = None
        
        return representation

