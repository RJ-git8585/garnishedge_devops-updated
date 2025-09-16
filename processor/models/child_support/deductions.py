
from django.db import models

class Deductions(models.Model):
    type = models.CharField(max_length=255)
    status = models.BooleanField(max_length=250, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = "deductions"
        verbose_name= "deductions"