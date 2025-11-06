from django.db import models

class GarnishmentFeesRules(models.Model):
    rule = models.CharField(max_length=255, unique=True)  
    maximum_fee_deduction = models.CharField(max_length=255)
    per_pay_period = models.DecimalField(max_digits=12, decimal_places=2)
    per_month = models.DecimalField(max_digits=12, decimal_places=2)
    per_remittance = models.DecimalField(max_digits=12, decimal_places=2)
    effective_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['rule'])
        ]
        db_table = "garnishment_fees_rules"
        verbose_name ="garnishment_fees_rules"

    def __str__(self):
        return self.rule
