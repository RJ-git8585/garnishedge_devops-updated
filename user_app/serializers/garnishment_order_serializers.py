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
        if value:
            return {
                "ee_id": value.ee_id,
                "ssn": value.ssn,
            }
        return None

    def to_internal_value(self, data):
        # if dict is passed
        if isinstance(data, dict):
            ee_id = data.get("ee_id")
            ssn = data.get("ssn")
            try:
                if ee_id:
                    return EmployeeDetail.objects.get(ee_id=ee_id)
                if ssn:
                    return EmployeeDetail.objects.get(ssn=ssn)
            except EmployeeDetail.DoesNotExist:
                raise serializers.ValidationError(
                    {self.field_name: f"Employee not found for {data}"}
                )
        # if plain string is passed (backward compatibility → treat as SSN)
        try:
            return EmployeeDetail.objects.get(ssn=data)
        except EmployeeDetail.DoesNotExist:
            raise serializers.ValidationError(
                {self.field_name: f"Employee with SSN '{data}' not found"}
            )


class StateField(serializers.Field):
    def to_representation(self, value: State):
        return value.state if value else None

    def to_internal_value(self, data):
        try:
            return State.objects.get(state__iexact=data)
        except State.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"State '{data}' not found"})


class GarnishmentTypeField(serializers.Field):
    def to_representation(self, value: GarnishmentType):
        return value.type if value else None

    def to_internal_value(self, data):
        try:
            return GarnishmentType.objects.get(type__iexact=data)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError({self.field_name: f"Garnishment type '{data}' not found"})


# ---------- Serializer ----------
class GarnishmentOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for GarnishmentOrder.
    - GET: returns human-readable fields (ssn, ee_id, state codes, garnishment type).
    - POST/PUT: accepts natural keys (ssn or ee_id for employee, state codes, garnishment type).
    """

    ssn = EmployeeField(source="employee")   # maps to FK employee
    work_state = StateField()
    issuing_state = StateField()
    garnishment_type = GarnishmentTypeField()
    ee_id = serializers.SerializerMethodField(read_only=True)  # ✅ make read-only

    class Meta:
        model = GarnishmentOrder
        fields = [
            "id", "case_id",
            "ssn", "ee_id",
            "work_state", "issuing_state", "garnishment_type",
            "garnishment_fees", "payee",
            "override_amount", "override_start_date", "override_stop_date", "paid_till_date",
            "is_consumer_debt",
            "issued_date", "received_date", "start_date", "stop_date",
            "ordered_amount", "garnishing_authority", "withholding_amount",
            "arrear_greater_than_12_weeks", "arrear_amount",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "ee_id"]

    def get_ee_id(self, obj):
        return obj.employee.ee_id if obj.employee else None
