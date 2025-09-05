from django.db import models


class PayPeriod(models.Model):
    pp_id = models.AutoField(primary_key=True,db_index=True)
    name = models.CharField(max_length=50, unique=True,db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        db_table ="payperiod"
        verbose_name ="payperiod"