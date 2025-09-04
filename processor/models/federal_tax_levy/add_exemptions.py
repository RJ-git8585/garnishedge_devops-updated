from django.db import models

class AddExemptions(models.Model):
    year = models.ForeignKey("processor.IRSPublication", on_delete=models.CASCADE,db_index=True)
    fs = models.ForeignKey("processor.FedFilingStatus", on_delete=models.CASCADE,db_index=True)
    num_exemptions = models.PositiveIntegerField()
    daily = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    weekly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    biweekly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    semimonthly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    monthly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = "add_exemptions"
        verbose_name ="add_exemptions"
        unique_together = ('year', 'fs', 'num_exemptions')
        