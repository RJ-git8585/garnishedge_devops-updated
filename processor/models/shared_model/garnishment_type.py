from django.db import models

class GarnishmentType(models.Model):
    type = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.type

    class Meta:
        db_table = "garnishment_type"
        verbose_name ="garnishment_type"

