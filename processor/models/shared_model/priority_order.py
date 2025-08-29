from django.db import models
from .garnishment_type import GarnishmentType

class PriorityOrders(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE,db_index=True)
    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE,db_index=True)
    priority_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "priority_order"
        verbose_name ="priority_order"