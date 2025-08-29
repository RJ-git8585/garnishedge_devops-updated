from django.db import models
from .withholding_rules import WithholdingRules

class WithholdingLimit(models.Model):
    
    rule = models.ForeignKey(
        WithholdingRules, 
        on_delete=models.CASCADE, 
        related_name='withholding_limits',
        db_index=True,
        db_column='rule_id' 
    )
    wl = models.CharField(max_length=10)
    supports_2nd_family = models.BooleanField( null=True, blank=True)
    arrears_of_more_than_12_weeks = models.BooleanField( null=True, blank=True)
    number_of_orders = models.CharField(max_length=10, null=True, blank=True)
    weekly_de_code = models.CharField(max_length=10, null=True, blank=True)
    work_state = models.CharField(max_length=10, null=True, blank=True)
    issuing_state = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "withholding_limit"
