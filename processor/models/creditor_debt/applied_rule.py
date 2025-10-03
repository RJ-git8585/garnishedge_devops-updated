from django.db import models

class CreditorDebtAppliedRule(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    pay_period  = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE,db_index=True)

    ee_id = models.CharField(max_length=255, blank=True, null=True)
    case_id = models.CharField(max_length=255, blank=True, null=True)
    withholding_cap = models.CharField(max_length=250, blank=True, null=True)
    withholding_basis = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['pay_period', 'state']),
        ]
        db_table = "creditor_debt_applied_rule"
        verbose_name = "creditor_debt_applied_rule"

