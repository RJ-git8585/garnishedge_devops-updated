from rest_framework import serializers
from user_app.models.iwo_pdf.iwo_pdf_extraction import WithholdingOrderData
from user_app.models import EmployeeDetail, EmployerProfile, SDU,GarnishmentOrder
from processor.models import State,GarnishmentType


class WithholdingOrderDataSerializers(serializers.ModelSerializer):
    class Meta:
        model = WithholdingOrderData
        fields = '__all__'


class GarnishmentOrderSerializer(serializers.ModelSerializer):
    # Accept readable fields instead of IDs
    employee_ssn = serializers.CharField(write_only=True)
    employer_name = serializers.CharField(write_only=True, required=False, allow_null=True)
    work_state_code = serializers.CharField(write_only=True)
    issuing_state_code = serializers.CharField(write_only=True)
    sdu_name = serializers.CharField(write_only=True)
    garnishment_type_name = serializers.CharField(write_only=True)  

    # Show nested details on response
    employee = serializers.StringRelatedField(read_only=True)
    employer = serializers.StringRelatedField(read_only=True)
    work_state = serializers.StringRelatedField(read_only=True)
    issuing_state = serializers.StringRelatedField(read_only=True)
    sdu = serializers.StringRelatedField(read_only=True)
    garnishment_type = serializers.StringRelatedField(read_only=True)  

    class Meta:
        model = GarnishmentOrder
        fields = [
            "id", "case_id",
            "employee", "employee_ssn",
            "employer", "employer_name",
            "work_state", "work_state_code",
            "issuing_state", "issuing_state_code",
            "sdu", "sdu_name",
            "garnishment_type", "garnishment_type_name", 
            "is_consumer_debt",
            "issued_date", "received_date", "start_date", "stop_date",
            "ordered_amount", "arrear_gt_12_weeks",
            "fein", "garnishing_authority", "withholding_amount",
            "arrear_greater_than_12_weeks", "arrear_amount",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        # Pop write-only fields
        employee_ssn = validated_data.pop("employee_ssn")
        employer_name = validated_data.pop("employer_name", None)
        work_state_code = validated_data.pop("work_state_code")
        issuing_state_code = validated_data.pop("issuing_state_code")
        sdu_name = validated_data.pop("sdu_name")
        garnishment_type_name = validated_data.pop("garnishment_type_name")

        # Resolve FKs
        try:
            employee = EmployeeDetail.objects.get(ssn=employee_ssn)
        except EmployeeDetail.DoesNotExist:
            raise serializers.ValidationError({"employee_ssn": "Employee not found with this SSN"})

        employer = None
        if employer_name:
            employer = EmployerProfile.objects.filter(name__iexact=employer_name).first()
            if not employer:
                raise serializers.ValidationError({"employer_name": "Employer not found with this name"})

        try:
            work_state = State.objects.get(code__iexact=work_state_code)
        except State.DoesNotExist:
            raise serializers.ValidationError({"work_state_code": "Invalid work state code"})

        try:
            issuing_state = State.objects.get(code__iexact=issuing_state_code)
        except State.DoesNotExist:
            raise serializers.ValidationError({"issuing_state_code": "Invalid issuing state code"})

        try:
            sdu = SDU.objects.get(name=sdu_name)
        except SDU.DoesNotExist:
            raise serializers.ValidationError({"sdu_name": "SDU not found"})

        try:
            garnishment_type = GarnishmentType.objects.get(name__ieaxct=garnishment_type_name)
        except GarnishmentType.DoesNotExist:
            raise serializers.ValidationError({"garnishment_type_name": "Invalid garnishment type"})

        return GarnishmentOrder.objects.create(
            employee=employee,
            employer=employer,
            work_state=work_state,
            issuing_state=issuing_state,
            sdu=sdu,
            garnishment_type=garnishment_type,
            **validated_data
        )

    def update(self, instance, validated_data):
        # Reuse same resolution logic if fields provided
        if "employee_ssn" in validated_data:
            ssn = validated_data.pop("employee_ssn")
            instance.employee = EmployeeDetail.objects.get(ssn__ieaxct=ssn)

        if "employer_name" in validated_data:
            name = validated_data.pop("employer_name")
            instance.employer = EmployerProfile.objects.get(name__ieac=name)

        if "work_state_code" in validated_data:
            code = validated_data.pop("work_state_code")
            instance.work_state = State.objects.get(code=code)

        if "issuing_state_code" in validated_data:
            code = validated_data.pop("issuing_state_code")
            instance.issuing_state = State.objects.get(code=code)

        if "sdu_name" in validated_data:
            name = validated_data.pop("sdu_name")
            instance.sdu = SDU.objects.get(name=name)

        if "garnishment_type_name" in validated_data: 
            name = validated_data.pop("garnishment_type_name")
            instance.garnishment_type = GarnishmentType.objects.get(name=name)

        # Update remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
