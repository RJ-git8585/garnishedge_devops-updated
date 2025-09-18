from django.db import models
from processor.models.shared_model.state import State

class SDU(models.Model):
    """
    State Disbursement Unit - where child support or garnishment payments are sent.
    """
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="sdus")
    case_id = models.ForeignKey(
        'user_app.GarnishmentOrder', on_delete=models.CASCADE, related_name="sdus"
    )
    payee = models.CharField(max_length=255)
    address = models.CharField(max_length=255,blank=True,null=True)
    contact = models.CharField(max_length=255,blank=True,null=True)
    fips_code = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["state_id"]),
            models.Index(fields=["case_id"]),
        ]
        db_table = "sdu"
