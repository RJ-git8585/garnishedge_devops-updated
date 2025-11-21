from django.conf import settings
from rest_framework import serializers


class ChangeLogQuerySerializer(serializers.Serializer):
    """
    Validates query parameters for the CDC change log endpoint.
    """

    source = serializers.CharField(
        required=False,
        default="all",
        help_text="Key that maps to a configured CDC capture instance, or 'all' to query all tables."
    )
    start_at = serializers.DateTimeField(required=False, help_text="UTC timestamp (ISO-8601) that maps to the earliest LSN.")
    end_at = serializers.DateTimeField(required=False, help_text="UTC timestamp (ISO-8601) that maps to the latest LSN.")
    operation = serializers.ChoiceField(
        required=False,
        choices=["insert", "delete", "update_after", "update_before"],
        help_text="Filter by CDC operation verb."
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=2000, default=500)

    def validate_source(self, value: str) -> str:
        if value == "all":
            return value
        if value not in settings.CDC_CAPTURE_INSTANCES:
            raise serializers.ValidationError(
                f"Unknown CDC source '{value}'. Configure it via CDC_CAPTURE_INSTANCES or use 'all'."
            )
        return value

    def validate(self, data):
        start_at = data.get("start_at")
        end_at = data.get("end_at")
        if start_at and end_at and end_at < start_at:
            raise serializers.ValidationError("end_at must be greater than or equal to start_at.")
        if not settings.CDC_CAPTURE_INSTANCES:
            raise serializers.ValidationError(
                "CDC_CAPTURE_INSTANCES is not configured. Add at least one capture instance in settings."
            )
        return data

