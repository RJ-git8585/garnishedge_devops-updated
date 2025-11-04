from django.db import models
from .irs_publication import IRSPublication
from .filing_status import FedFilingStatus

class StdExemptions(models.Model):
    std_id = models.AutoField(primary_key=True)
    year = models.ForeignKey(IRSPublication, on_delete=models.CASCADE,db_index=True)
    fs = models.ForeignKey(FedFilingStatus, on_delete=models.CASCADE,db_index=True)
    pp = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE,db_index=True)
    
    num_exemptions = models.CharField(max_length=100, null=True, blank=True)
    exempt_amt = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = "std_exemptions"
        verbose_name = "std_exemptions"

        unique_together = ('year', 'fs', 'pp','num_exemptions')
