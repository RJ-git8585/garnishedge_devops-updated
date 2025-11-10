from django.db import models


class GarnishmentResult(models.Model):
    # ---- Batch Info ----
    batch_id = models.CharField(max_length=20)
    processed_at = models.DateTimeField(null=True, blank=True)

    # ---- Employee & Case Info ----
    ee = models.ForeignKey('user_app.EmployeeDetail', on_delete=models.CASCADE, related_name="garnishment_results")
    case = models.ForeignKey('user_app.GarnishmentOrder', on_delete=models.CASCADE, related_name="garnishment_results")

    # ---- Calculation Outputs ----
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_mandatory_deduction = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    disposable_earning = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    allowable_disposable_earning = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # ---- Case-based Garnishment Values ----
    ordered_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    arrear_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    withholding_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    withholding_arrear = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE, related_name="garnishment_results")
    withholding_limit_rule = models.CharField(max_length=100, null=True, blank=True)
    withholding_basis = models.CharField(max_length=100, null=True, blank=True)
    withholding_cap = models.CharField(max_length=100, null=True, blank=True)

    # ---- Fee / Notes ----
    garnishment_fees_note = models.TextField(null=True, blank=True)

    # ---- Audit Info ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "garnishment_result"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ee_id} - {self.case_id or 'No Case'} - {self.batch_id}"
