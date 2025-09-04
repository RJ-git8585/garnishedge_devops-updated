from django.db import models

class GarnishmentFeesRules(models.Model):
    rule = models.CharField(max_length=255, unique=True,db_index=True)  
    maximum_fee_deduction = models.CharField(max_length=255)
    per_pay_period = models.DecimalField(max_digits=12, decimal_places=2)
    per_month = models.DecimalField(max_digits=12, decimal_places=2)
    per_remittance = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "garnishment_fees_rules"
        verbose_name ="garnishment_fees_rules"
