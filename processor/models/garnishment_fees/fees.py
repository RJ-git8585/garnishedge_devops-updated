from django.db import models
from .fees_rule import GarnishmentFeesRules


class GarnishmentFees(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True,related_name="fees")
    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE,related_name="fees", db_index=True)
    pay_period = models.ForeignKey('PayPeriod', on_delete=models.CASCADE,related_name="fees", db_index=True)
    
    # Added unique related_name to avoid clash
    rule = models.ForeignKey(
        GarnishmentFeesRules,
        on_delete=models.CASCADE,
        related_name="garnishment_fees"
    )
    amount = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255)


    payable_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['garnishment_type']),
            models.Index(fields=['pay_period', 'state']),
        ]
        db_table = "garnishment_fees"
        verbose_name ="garnishment_fees"

    def __str__(self):
        return f"{self.rule.rule} - {self.state}"
