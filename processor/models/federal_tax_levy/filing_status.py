from django.db import models

class FedFilingStatus(models.Model):
    name = models.CharField(max_length=100, unique=True) 
    default_exempt_amt = models.FloatField(help_text="Default exempt amount for older/blind")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fed_filing_status"
        verbose_name ="fed_filing_status"

    def __str__(self):
        return self.name