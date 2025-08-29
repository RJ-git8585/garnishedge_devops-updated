from rest_framework import serializers
from user_app.models import Client, GarnishmentOrder,EmployeeDetail


class EmployeeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for EmployeeDetail.
    - Read: returns human-readable client_id.
    - Write: accepts client_id for FK resolution.
    """

    # Readable field (GET)
    client = serializers.CharField(source='client.client_id', read_only=True)

    # Writable field (POST/PUT/PATCH)
    client_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = EmployeeDetail
        fields = [
            "id", "ee_id",
            "client", "client_id",   # both read and write
            "ssn", "age", "is_blind",
            "home_state", "work_state", "gender",
            "number_of_exemptions", "filing_status", "marital_status",
            "number_of_student_default_loan", "number_of_dependent_child",
            "support_second_family", "spouse_age", "is_spouse_blind",
            "record_import", "record_updated",
            "garnishment_fees_status", "garnishment_fees_suspended_till",
            "number_of_active_garnishment", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "record_import", "record_updated"]

    def create(self, validated_data):
        client_id = validated_data.pop("client_id")

        try:
            client = Client.objects.get(client_id=client_id)
        except Client.DoesNotExist:
            raise serializers.ValidationError({"client_id": f"Client '{client_id}' not found"})

        return EmployeeDetail.objects.create(client=client, **validated_data)

    def update(self, instance, validated_data):
        client_id = validated_data.pop("client_id", None)
        if client_id:
            try:
                client = Client.objects.get(client_id=client_id)
                instance.client = client
            except Client.DoesNotExist:
                raise serializers.ValidationError({"client_id": f"Client '{client_id}' not found"})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

