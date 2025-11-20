from rest_framework import serializers
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
            "type",
            "event_type",
            "category",
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


class LetterTemplateFillSerializer(serializers.Serializer):
    """
    Serializer for filling template variables with values.
    Automatically fetches data from database using employee_id and optional order_id.
    """
    template_id = serializers.IntegerField(required=True)
    
    employee_id = serializers.CharField(
        required=True,
        help_text="Employee ID (ee_id) or primary key. System will auto-fetch employee, order, and Payee data."
    )
    order_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional: Order ID (case_id) or primary key. If not provided, uses most recent active order for the employee."
    )
    
    format = serializers.ChoiceField(
        choices=['pdf', 'doc', 'docx', 'txt', 'text'],
        default='pdf',
        required=False,
        help_text="Export format: pdf, doc, docx, txt, or text"
    )
    
    def validate(self, attrs):
        """
        Validate employee_id is provided and not empty.
        """
        employee_id = attrs.get('employee_id')
        
        # Clean up employee_id - remove empty strings
        if not employee_id or employee_id == '':
            raise serializers.ValidationError({
                'employee_id': ["Employee ID is required and cannot be empty."]
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