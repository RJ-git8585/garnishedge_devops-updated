from rest_framework import serializers
from user_app.models.iwo_pdf.iwo_pdf_extraction import WithholdingOrderData
from user_app.models import EmployeeDetail, EmployerProfile, SDU,GarnishmentOrder
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


class EmployeeField(serializers.Field):
    def to_representation(self, value: EmployeeDetail):
        # Only return SSN
        return value.ssn if value else None

    def to_internal_value(self, data):
        try:
            return EmployeeDetail.objects.get(ssn=data)
        except EmployeeDetail.DoesNotExist:
            raise serializers.ValidationError(
                {"employee": f"Employee with SSN '{data}' not found"}
            )


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
                employee = EmployeeDetail.objects.get(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employee
            except EmployeeDetail.DoesNotExist:
                raise serializers.ValidationError({"ee_id": "Employee with this ee_id not found"})
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Handle ee_id to ssn mapping
        if 'ee_id' in validated_data:
            try:
                employee = EmployeeDetail.objects.get(ee_id=validated_data.pop('ee_id'))
                validated_data['employee'] = employee
            except EmployeeDetail.DoesNotExist:
                raise serializers.ValidationError({"ee_id": "Employee with this ee_id not found"})
        
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
