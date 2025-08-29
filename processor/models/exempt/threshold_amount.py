
from django.db import models
from .exempt_config import ExemptConfig

class ThresholdAmount(models.Model):
    config = models.ForeignKey(ExemptConfig, on_delete=models.CASCADE,db_index=True)
    lower_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    lower_threshold_percent1 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    lower_threshold_percent2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    mid_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    mid_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    upper_threshold_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    upper_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_lower_to_upper_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_lower_to_mid_threshold_percent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    de_range_mid_to_upper_threshold_percent =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    exempt_amt = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    filing_status_percent =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="threshold_amount"
        verbose_name = "threshold_amount"

