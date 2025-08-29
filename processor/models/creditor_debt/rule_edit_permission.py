from django.db import models

class CreditorDebtRuleEditPermission(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    deduction_basis = models.CharField(max_length=255, blank=True, null=True)
    withholding_limit = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state'])
        ]
        db_table = "creditor_debt_rule_edit_permission"
        verbose_name= "creditor_debt_rule_edit_permission"
