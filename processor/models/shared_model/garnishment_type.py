from django.db import models

class GarnishmentType(models.Model):
    type = models.CharField(max_length=100, unique=True,db_index=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "garnishment_type"
        verbose_name ="garnishment_type"

