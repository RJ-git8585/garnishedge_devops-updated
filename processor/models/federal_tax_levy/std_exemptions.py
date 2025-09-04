from django.db import models

class StdExemptions(models.Model):
    year = models.ForeignKey('processor.IRSPublication', on_delete=models.CASCADE,db_index=True)
    fs = models.ForeignKey('processor.FedFilingStatus', on_delete=models.CASCADE,db_index=True)
    pp = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE,db_index=True)
    num_exemptions = models.CharField(max_length=100, null=True, blank=True)
    exempt_amt = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "std_exemptions"
        verbose_name = "std_exemptions"
        unique_together = ('year', 'fs', 'pp','num_exemptions')
