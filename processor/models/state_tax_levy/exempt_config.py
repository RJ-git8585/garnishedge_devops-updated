from django.db import models

class StateTaxLevyExemptAmtConfig(models.Model):
    state_config = models.ForeignKey(
        'processor.StateTaxLevyConfig',
        on_delete=models.CASCADE,
        related_name="state_tax_levy_exempt_amounts"
    )
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    pay_period = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE, db_index=True)
    minimum_hourly_wage_basis = models.CharField(max_length=255)
    minimum_wage_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    multiplier_lt = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_lt = models.CharField(max_length=1200,null=True, blank=True)
    lower_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=4)
    multiplier_ut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_ut = models.CharField(max_length=1200,null=True, blank=True)
    upper_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=4)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['pay_period', 'state']),
        ]
        db_table = "state_tax_levy_exempt_amt_config"
        verbose_name ="state_tax_levy_exempt_amt_config"
