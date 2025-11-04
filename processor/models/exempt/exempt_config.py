from django.db import models
from .exempt_rule import ExemptRule

class ExemptConfig(models.Model):
    rule =models.ForeignKey('processor.ExemptRule', on_delete=models.CASCADE,db_index=True)
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE,db_index=True)
    home_state = models.CharField(max_length=100,null=True, blank=True)
    pay_period = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE,db_index=True)
    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE,db_index=True)
    debt_type = models.CharField(max_length=100,null=True, blank=True)
    is_filing_status = models.BooleanField(default=False)
    wage_basis = models.CharField(max_length=100,null=True, blank=True)
    wage_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    percent_limit = models.IntegerField(null=True, blank=True)
    garn_start_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True, help_text="Date when this configuration becomes active. If null, config is active immediately.")
    ftb_type = models.CharField(max_length=100,null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table ="exempt_config"
        verbose_name = "exempt_config"

