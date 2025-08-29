from django.db import models
from .rule import CreditorDebtRule


class CreditorDebtExemptAmtConfig(models.Model):
    state_config = models.ForeignKey(
        CreditorDebtRule,
        on_delete=models.CASCADE,
        related_name="creditor_debt_exempt_amounts"
    )
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    pay_period  = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE,db_index=True)
    minimum_hourly_wage_basis = models.CharField(
        max_length=20, null=True, blank=True)
    minimum_wage_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    multiplier_lt = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_lt = models.CharField(
        max_length=100, null=True, blank=True)
    lower_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    lower_threshold_percent1 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    lower_threshold_percent2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    multiplier_mid = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_mid = models.CharField(
        max_length=100, null=True, blank=True)
    mid_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    mid_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    multiplier_ut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_ut = models.CharField(
        max_length=100, null=True, blank=True)
    upper_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    upper_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_lower_to_upper_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_lower_to_mid_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_mid_to_upper_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deducted_basis_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    is_filing_status = models.CharField(max_length=100, null=True, blank=True)
    filing_status_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    exempt_amt = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['pay_period', 'state']),
        ]
        db_table = "creditor_debt_exempt_amt_config"
        verbose_name = "creditor_debt_exempt_amt_config"
 
