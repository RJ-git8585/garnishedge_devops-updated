from django.db import models
from .garnishment_type import GarnishmentType

class MultipleGarnPriorityOrders(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE,db_index=True)
    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE,db_index=True)
    priority_order = models.IntegerField()
    effective_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "multiple_garn_priority_order"
        verbose_name ="multiple_garn_priority_order"