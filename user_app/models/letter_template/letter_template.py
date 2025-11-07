from django.db import models


class LetterTemplate(models.Model):
    """
    Model to store letter templates with HTML content and variable placeholders.
    """
    name = models.CharField(max_length=255, unique=True, help_text="Unique name for the letter template")
    description = models.TextField(blank=True, null=True, help_text="Description of the letter template")
    html_content = models.TextField(help_text="HTML content of the letter template with variable placeholders like {{variable_name}}")
    is_active = models.BooleanField(default=True, help_text="Whether the template is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "letter_template"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def get_variable_names(self):
        """
        Extract variable names from HTML content (variables in {{variable_name}} format).
        """
        import re
        pattern = r'\{\{(\w+)\}\}'
        return list(set(re.findall(pattern, self.html_content)))

