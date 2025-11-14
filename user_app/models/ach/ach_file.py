from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ACHFile(models.Model):
    """
    Model to store metadata for generated ACH files.
    """
    FILE_FORMAT_CHOICES = [
        ('txt', 'TXT'),
        ('pdf', 'PDF'),
        ('xml', 'XML'),
    ]

    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES, default='txt')
    file_url = models.URLField(blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)  # Size in bytes
    
    # Generation metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generated_ach_files'
    )
    
    # Payment details
    pay_date = models.DateField()
    agency_payee = models.CharField(max_length=255, blank=True, null=True)
    total_payment_count = models.IntegerField(default=0)
    total_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # File details
    batch_id = models.CharField(max_length=50, blank=True, null=True)
    file_id_modifier = models.CharField(max_length=1, blank=True, null=True)
    
    # Associated orders (stored as JSON or comma-separated)
    associated_case_ids = models.TextField(blank=True, null=True)  # JSON array or comma-separated
    
    # Transaction references
    transaction_references = models.TextField(blank=True, null=True)  # JSON array
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Additional metadata
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ach_file'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['pay_date']),
            models.Index(fields=['generated_at']),
            models.Index(fields=['batch_id']),
        ]

    def __str__(self):
        return f"{self.file_name} - {self.pay_date} - {self.total_payment_count} payments"

