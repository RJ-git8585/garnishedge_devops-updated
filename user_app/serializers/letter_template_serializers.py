from rest_framework import serializers
from user_app.models import LetterTemplate


class LetterTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for LetterTemplate model.
    """
    variable_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LetterTemplate
        fields = [
            "id",
            "name",
            "description",
            "html_content",
            "variables",
            "variable_names",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at", "variable_names")

    def get_variable_names(self, obj):
        """
        Extract and return variable names from HTML content.
        """
        return obj.get_variable_names()

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
    """
    template_id = serializers.IntegerField(required=True)
    variable_values = serializers.DictField(
        required=True,
        help_text="Dictionary of variable names and their values to fill in the template"
    )
    format = serializers.ChoiceField(
        choices=['pdf', 'doc', 'docx', 'txt'],
        default='pdf',
        required=False,
        help_text="Export format: pdf, doc, docx, or txt"
    )

