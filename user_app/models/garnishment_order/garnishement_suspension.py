from django.db import models
from .garnishment_orders import GarnishmentOrder


class GarnishmentSuspension(models.Model):
    """
    Represents a temporary halt of garnishment for a specific order.
    """
    order = models.ForeignKey(
        GarnishmentOrder, on_delete=models.CASCADE, related_name="suspensions"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    effective_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["start_date", "end_date"]),
        ]
        db_table = "garnishment_suspension"

    def __str__(self):
        return f"Suspension for Order {self.order.id} ({self.start_date} - {self.end_date})"

