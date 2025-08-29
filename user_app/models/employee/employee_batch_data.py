from django.db import models

class EmployeeBatchData(models.Model):
    ee_id = models.CharField(max_length=255, unique=True)
    case_id = models.CharField(max_length=255, unique=True)
    work_state = models.CharField(max_length=255)
    no_of_exemption_including_self = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    pay_period = models.CharField(max_length=255, null=True, blank=True)
    filing_status = models.CharField(max_length=255, null=True, blank=True)
    age = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    is_blind = models.BooleanField(null=True, blank=True)
    is_spouse_blind = models.BooleanField(null=True, blank=True)
    spouse_age = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    support_second_family = models.CharField(max_length=255,null=True, blank=True)
    no_of_student_default_loan = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    arrears_greater_than_12_weeks = models.CharField(max_length=255,null=True, blank=True)
    no_of_dependent_exemption = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['case_id']),
            models.Index(fields=['ee_id', 'case_id']),
        ]

        db_table = "employee_batch_data"

    def __str__(self):
        return f"Employee {self.ee_id} - Case {self.case_id}"

