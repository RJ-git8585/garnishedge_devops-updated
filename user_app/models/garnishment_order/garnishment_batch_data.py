from django.db import models

class GarnishmentBatchData(models.Model):
    employee_case = models.OneToOneField(
        'user_app.EmployeeBatchData',
        to_field='case_id',
        on_delete=models.CASCADE,
        related_name='garnishment_data'
    )
    ee_id = models.CharField(max_length=255)
    case_id = models.CharField(max_length=255, unique=True)
    garnishment_type = models.CharField(max_length=255)
    ordered_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    arrear_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    current_medical_support = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    past_due_medical_support = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    current_spousal_support = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    past_due_spousal_support = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ee_id']),
            models.Index(fields=['ee_id', 'case_id']),
        ]
        db_table = "garnishment_batch_data"

