from django.db import models
from .threshold_amount import ThresholdAmount

class ThresholdCondition(models.Model):
    threshold = models.ForeignKey(ThresholdAmount, on_delete=models.CASCADE,db_index=True)
    multiplier_lt = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_lt = models.CharField(max_length=100, null=True, blank=True)
    multiplier_mid = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_mid = models.CharField(max_length=100, null=True, blank=True)
    multiplier_ut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    condition_expression_ut = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="threshold_condition"
        verbose_name ="threshold_condition"

