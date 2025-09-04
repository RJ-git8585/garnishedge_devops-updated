from django.db import models


class PayPeriod(models.Model):
    name = models.CharField(max_length=50, unique=True,db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="payperiod"
        verbose_name ="payperiod"