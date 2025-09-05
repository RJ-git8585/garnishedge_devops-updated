from django.db import models
from ..peo.peo import PEO
from user_app.utils import HashValue
from processor.models.shared_model.state import State

class Client(models.Model):
    client_id = models.CharField(max_length=50, unique=True)
    peo = models.ForeignKey(PEO, on_delete=models.CASCADE, related_name="clients")
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="clients")
    pay_period = models.ForeignKey('processor.PayPeriod', on_delete=models.CASCADE, related_name="clients")
    legal_name = models.CharField(max_length=255)
    dba = models.CharField(max_length=255)
    industry_type = models.CharField(max_length=100)
    tax_id = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['client_id']),
        ]

        db_table = "client"


    def save(self, *args, **kwargs):
        if self.tax_id and len(self.tax_id) != 64:
            self.tax_id = HashValue.hash_value(self.tax_id)
        super().save(*args, **kwargs)


