from django.db import models


class AchBankDetails(models.Model):

    company_id = models.CharField(
        max_length=20
    )

    originating_routing_number = models.CharField(
        max_length=9,
        help_text="Immediate receiving routing number"
    )

    originating_bank_name = models.CharField(
        max_length=255,
        default="Wells Fargo Garnishment"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.company_id} - {self.garnishment_type} ({self.pay_date})"
