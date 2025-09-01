from django.db import models
from user_app.utils import HashValue

class EmployeeDetail(models.Model):
    ee_id = models.CharField(max_length=255, unique=True)
    client = models.ForeignKey('user_app.Client', on_delete=models.CASCADE, related_name="employees")
    ssn = models.CharField(max_length=64)
    age = models.IntegerField()
    is_blind = models.BooleanField(null=True, blank=True)
    home_state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="employees_home")
    work_state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="employees_work")
    gender = models.CharField(max_length=255, null=True, blank=True)
    number_of_exemptions = models.IntegerField()
    filing_status = models.ForeignKey('processor.FedFilingStatus', on_delete=models.CASCADE, related_name="employees")
    marital_status = models.CharField(max_length=255)
    number_of_student_default_loan = models.IntegerField()
    number_of_dependent_child = models.IntegerField()
    support_second_family = models.BooleanField(default=False)
    spouse_age = models.IntegerField(null=True, blank=True)
    is_spouse_blind = models.BooleanField(null=True, blank=True)
    record_import = models.DateTimeField(auto_now_add=True)
    record_updated = models.DateTimeField(auto_now=True)  
    garnishment_fees_status = models.BooleanField(default=False)
    garnishment_fees_suspended_till = models.DateField(null=True, blank=True) 
    number_of_active_garnishment = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ee_id'])
        ]
        db_table = "employee_detail"

    def __str__(self):
        return f"{self.home_state} {self.work_state} ({self.ssn})"

    # def save(self, *args, **kwargs):
    #     if self.ssn and len(self.ssn) != 64:  
    #         self.ssn = HashValue.hash_value(self.ssn)
    #     super().save(*args, **kwargs)
