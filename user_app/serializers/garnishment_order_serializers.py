from rest_framework import serializers
from user_app.models.iwo_pdf.iwo_pdf_extraction import WithholdingOrderData
from user_app.models import EmployeeDetail, EmployerProfile, SDU,GarnishmentOrder
from processor.models import State,GarnishmentType


class WithholdingOrderDataSerializers(serializers.ModelSerializer):
    class Meta:
        model = WithholdingOrderData
        fields = '__all__'


# ---------- Custom Field Types ----------

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

    class Meta:
        model = GarnishmentOrder
        fields = [
            "id",
            "case_id",
            "ssn",
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
