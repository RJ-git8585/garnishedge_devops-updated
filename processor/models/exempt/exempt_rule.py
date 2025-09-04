from django.db import models

class ExemptRule(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    rule_id = models.IntegerField(unique=True,db_index=True)
    deduction_basis = models.CharField(max_length=255, blank=True, null=True)
    withholding_limit = models.CharField(max_length=255, blank=True, null=True)
    rule = models.CharField(max_length=2500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exempt_rule"
        verbose_name = "exempt_rule"

