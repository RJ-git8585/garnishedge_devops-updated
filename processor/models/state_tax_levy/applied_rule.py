from django.db import models


class StateTaxLevyAppliedRule(models.Model):
    ee_id = models.CharField(max_length=1000, blank=True, null=True,db_index=True)
    case_id = models.CharField(max_length=1000, blank=True, null=True,db_index=True)
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    pay_period = models.CharField(max_length=1000)
    deduction_basis = models.CharField(max_length=1000, blank=True, null=True)
    withholding_cap = models.CharField(max_length=1000, blank=True, null=True)
    withholding_limit = models.CharField(
        max_length=1000, blank=True, null=True)
    withholding_basis = models.CharField(
        max_length=1000, blank=True, null=True)
    withholding_limit_rule = models.CharField(
        max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "state_tax_levy_applied_rule"
        verbose_name ="state_tax_levy_applied_rule"