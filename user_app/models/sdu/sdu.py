from django.db import models
from processor.models.shared_model.state import State

class SDU(models.Model):
    """
    State Disbursement Unit - where child support or garnishment payments are sent.
    """
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="sdus")
    order = models.ForeignKey(
        'user_app.GarnishmentOrder', on_delete=models.CASCADE, related_name="sdus"
    )
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    fips_code = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sdu"
