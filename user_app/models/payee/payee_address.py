from django.db import models
from .payee import PayeeDetails

class PayeeAddress(models.Model):
    payee = models.OneToOneField(PayeeDetails, on_delete=models.CASCADE, related_name='address')
    address_1 = models.CharField(max_length=255, blank=True, null=True)
    address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="payee_addresses")
    zip_code = models.IntegerField(blank=True, null=True)
    zip_plus_4 = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'payee_address'
        verbose_name = 'Payee Address'
        verbose_name_plural = 'Payee Addresses'

    def __str__(self):
        return f"{self.address_1}, {self.city}, {self.state}"


