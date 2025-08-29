from django.db import models

class StateTaxLevyConfig(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    deduction_basis = models.CharField(max_length=255, blank=True, null=True)
    withholding_limit = models.CharField(max_length=255, blank=True, null=True)
    withholding_limit_rule = models.CharField(
        max_length=455, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state'])
        ]
        db_table = "state_tax_levy_config"
        verbose_name ="state_tax_levy_config"