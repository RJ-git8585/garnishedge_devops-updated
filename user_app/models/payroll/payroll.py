from django.db import models


class Payroll(models.Model):
    state = models.ForeignKey("processor.State", on_delete=models.CASCADE, related_name="payrolls")
    ee_id = models.ForeignKey("user_app.EmployeeDetail", on_delete=models.CASCADE, related_name="payrolls",db_index=True)
    payroll_date = models.DateField()
    pay_date = models.DateField()
    gross_pay = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    net_pay = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    federal_income_tax = models.DecimalField(
        max_digits=250, decimal_places=2)
    local_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    medicare_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    social_security = models.CharField(max_length=255)
    deduction_sdi = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_medical_insurance = models.DecimalField(
        max_digits=250, decimal_places=2)
    deduction_401k = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_union_dues = models.DecimalField(
        max_digits=250, decimal_places=2)
    deduction_voluntary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    type = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:

        db_table = "payroll"
