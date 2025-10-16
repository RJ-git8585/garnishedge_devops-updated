from rest_framework import serializers
from user_app.models.iwo_pdf.iwo_pdf_extraction import WithholdingOrderData
from user_app.models import EmployeeDetails, EmployerProfile, SDU,GarnishmentOrder
from processor.models import State,GarnishmentType
from datetime import datetime


class WithholdingOrderDataSerializers(serializers.ModelSerializer):
    class Meta:
        model = WithholdingOrderData
        fields = '__all__'


# ---------- Custom Field Types ----------

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
        
        if not isinstance(data, str):
            raise serializers.ValidationError(
                "Date must be a string. Use MM-DD-YYYY format (e.g., 01-20-2024)."
            )
        
        # Try different date formats
        date_formats = [
            "%m-%d-%Y",  # MM-DD-YYYY
            "%Y-%m-%d",  # YYYY-MM-DD (standard format)
            "%m/%d/%Y",  # MM/DD/YYYY
            "%Y/%m/%d",  # YYYY/MM/DD
        ]
        
        for date_format in date_formats:
            try:
                date_obj = datetime.strptime(data, date_format)
                return date_obj.date()
            except ValueError:
                continue
        
        # If none of the formats work, raise validation error
        raise serializers.ValidationError(
            "Date has wrong format. Use MM-DD-YYYY format (e.g., 01-20-2024)."
        )


class EmployeeField(serializers.Field):
    def to_representation(self, value: EmployeeDetails):
        # Only return SSN
        return value.ssn if value else None

    def to_internal_value(self, data):
        try:
            # First try to get a single employee
            return EmployeeDetails.objects.get(ssn=data)
        except EmployeeDetails.DoesNotExist:
            raise serializers.ValidationError(
                {"employee": f"Employee with SSN '{data}' not found"}
            )
        except EmployeeDetails.MultipleObjectsReturned:
            # If multiple employees with same SSN, get the first one
            # You might want to add additional logic here to determine which one to use
            employees = EmployeeDetails.objects.filter(ssn=data)
            return employees.first()


class StateField(serializers.Field):
    def to_representation(self, value: State):
        return value.state if value else None

    def to_internal_value(self, data):
        try:
            return State.objects.get(state__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError(
                {"state": f"State '{data}' not found"}
            )
        except State.MultipleObjectsReturned:
            # If multiple states with same name, get the first one
            states = State.objects.filter(state__iexact=data)
            return states.first()


class GarnishmentTypeField(serializers.Field):
    def to_representation(self, value: GarnishmentType):
        return value.type if value else None

    def to_internal_value(self, data):
        try:
            return GarnishmentType.objects.get(type__iexact=data)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError(
                {"garnishment_type": f"Garnishment type '{data}' not found"}
            )
        except GarnishmentType.MultipleObjectsReturned:
            # If multiple garnishment types with same name, get the first one
            garnishment_types = GarnishmentType.objects.filter(type__iexact=data)
            return garnishment_types.first()


# ---------- Serializer ----------

class GarnishmentOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for GarnishmentOrder.
    - GET: returns human-readable fields (ssn, state codes, garnishment type).
    - POST/PUT: accepts natural keys.
    """

    ssn = EmployeeField(source="employee")   # map to model field "employee"
    issuing_state = StateField()
    garnishment_type = GarnishmentTypeField()
    
    # Custom date fields that accept MM-DD-YYYY format
    issued_date = CustomDateField(allow_null=True, required=False)
    received_date = CustomDateField(allow_null=True, required=False)
    start_date = CustomDateField(allow_null=True, required=False)
    stop_date = CustomDateField(allow_null=True, required=False)
    override_start_date = CustomDateField(allow_null=True, required=False)
    override_stop_date = CustomDateField(allow_null=True, required=False)
    paid_till_date = CustomDateField(allow_null=True, required=False)
    
    # Handle field name mapping from payload
    ee_id = serializers.CharField(write_only=True, required=False)
    
    def create(self, validated_data):
        # Handle ee_id to ssn mapping
        if 'ee_id' in validated_data:
            # If ee_id is provided, try to find employee by ee_id
            try:
                employee = EmployeeDetails.objects.get(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employee
            except EmployeeDetails.DoesNotExist:
                raise serializers.ValidationError({"ee_id": "Employee with this ee_id not found"})
            except EmployeeDetails.MultipleObjectsReturned:
                # If multiple employees with same ee_id, get the first one
                employees = EmployeeDetails.objects.filter(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employees.first()
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Handle ee_id to ssn mapping
        if 'ee_id' in validated_data:
            try:
                employee = EmployeeDetails.objects.get(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employee
            except EmployeeDetails.DoesNotExist:
                raise serializers.ValidationError({"ee_id": "Employee with this ee_id not found"})
            except EmployeeDetails.MultipleObjectsReturned:
                # If multiple employees with same ee_id, get the first one
                employees = EmployeeDetails.objects.filter(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employees.first()
        
        return super().update(instance, validated_data)

    class Meta:
        model = GarnishmentOrder
        fields = [
            "id",
            "case_id",
            "ssn",
            "ee_id",  # Add ee_id field for payload compatibility
            "issuing_state",
            "garnishment_type",
            "garnishment_fees",
            "payee",
            "override_amount",
            "override_start_date",
            "override_stop_date",
            "paid_till_date",
            "is_consumer_debt",
            "issued_date",
            "received_date",
            "start_date",
            "stop_date",
            "ordered_amount",
            "garnishing_authority",
            "withholding_amount",
            "current_child_support",
            "current_medical_support",
            "child_support_arrear",
            "medical_support_arrear",
            "current_spousal_support",
            "spousal_support_arrear",
            "fips_code",
            "arrear_greater_than_12_weeks",
            "arrear_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
