from django.db import models


class Payroll(models.Model):
    state = models.ForeignKey("processor.State", on_delete=models.CASCADE, related_name="payrolls")
    ee_id = models.ForeignKey("user_app.EmployeeDetail", on_delete=models.CASCADE, related_name="payrolls")
    client_id = models.ForeignKey("user_app.Client", on_delete=models.CASCADE, related_name="payrolls")
    batch_id = models.CharField(max_length=255, null=True, blank=True)
    pay_period = models.CharField(max_length=255, null=True, blank=True)
    payroll_date = models.DateField()
    pay_date = models.DateField(null=True, blank=True)
    wages = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    commission_and_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    non_accountable_allowances = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    gross_pay = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    net_pay = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    federal_income_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    state_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    local_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    medicare_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    social_security = models.CharField(max_length=255, null=True, blank=True)
    social_security_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    wilmington_tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    california_sdi = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_sdi = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    medical_insurance_pretax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_medical_insurance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    life_insurance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    retirement_401k = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_401k = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    industrial_insurance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    union_dues = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_union_dues = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deduction_voluntary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ee_id'])
        ]
        db_table = "payroll"
