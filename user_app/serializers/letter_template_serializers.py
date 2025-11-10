from rest_framework import serializers
from rest_framework.fields import empty
from user_app.models import LetterTemplate


class LetterTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for LetterTemplate model.
    """

    class Meta:
        model = LetterTemplate
        fields = [
            "id",
            "name",
            "description",
            "html_content",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        """
        Ensure name uniqueness.
        """
        if self.instance and self.instance.name == value:
            return value
        
        if LetterTemplate.objects.filter(name=value).exists():
            raise serializers.ValidationError("A letter template with this name already exists.")
        return value


class OptionalDictField(serializers.DictField):
    """
    Custom DictField that allows the field to be completely omitted.
    """
    def to_internal_value(self, data):
        if data is empty or data is None:
            return {}
        return super().to_internal_value(data)


class LetterTemplateFillSerializer(serializers.Serializer):
    """
    Serializer for filling template variables with values.
    Supports two modes:
    1. Automatic mode: Provide employee_id (and optionally order_id) to auto-populate from database
    2. Manual mode: Provide variable_values dictionary for manual variable mapping
    """
    template_id = serializers.IntegerField(required=True)
    
    # Automatic data fetching mode
    employee_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Employee ID (ee_id) or primary key. If provided, system will auto-fetch employee, order, and Payee data."
    )
    order_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional: Order ID (case_id) or primary key. If not provided, uses most recent active order for the employee."
    )
    
    # Manual variable mapping mode (for backward compatibility)
    variable_values = OptionalDictField(
        required=False,
        allow_null=True,
        allow_empty=True,
        help_text="Dictionary of variable names and their values to fill in the template. Used when employee_id is not provided."
    )
    
    format = serializers.ChoiceField(
        choices=['pdf', 'doc', 'docx', 'txt', 'text'],
        default='pdf',
        required=False,
        help_text="Export format: pdf, doc, docx, txt, or text"
    )
    
    def validate(self, attrs):
        """
        Validate that either employee_id or variable_values is provided.
        """
        employee_id = attrs.get('employee_id')
        variable_values = attrs.get('variable_values') or {}
        
        # Clean up employee_id - remove empty strings and None
        if not employee_id or employee_id == '':
            employee_id = None
            attrs['employee_id'] = None
        
        # Ensure variable_values is a dict
        if variable_values is None:
            variable_values = {}
            attrs['variable_values'] = {}
        
        # Validate that at least one is provided
        if not employee_id and not variable_values:
            raise serializers.ValidationError({
                'non_field_errors': ["Either 'employee_id' or 'variable_values' must be provided."]
            })
        
        return attrs


class LetterTemplateVariableValuesSerializer(serializers.Serializer):
    """
    Serializer for fetching template variable values for an employee.
    """
    employee_id = serializers.CharField(
        required=True,
        help_text="Employee ID (ee_id) or primary key"
    )
    order_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional: Order ID (case_id) or primary key. If not provided, uses most recent active order."
    )


class LetterTemplateExportSerializer(serializers.Serializer):
    """
    Serializer for exporting employee details, order, payee, and GarnishmentResult data.
    """
    format = serializers.ChoiceField(
        choices=['csv', 'txt'],
        default='csv',
        required=False,
        help_text="Export format: csv or txt (default: csv)"
    )