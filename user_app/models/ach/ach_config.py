from django.db import models


class AchGarnishmentConfig(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ("CCD", "CCD"),
        ("CTX", "CTX"),
        ("PPD", "PPD"),
    ]

    MEDICAL_SUPPORT_CHOICES = [
        ("N", "No"),
        ("Y", "Yes"),
    ]

    SERVICE_CLASS_CODE_CHOICES = [
        ("200", "Credit & Debit"),
        ("220", "Credits Only"),
        ("225", "Debits Only"),
    ]

    ACCOUNT_TYPE_CHOICES = [
        ("checking", "Checking"),
        ("savings", "Savings"),
    ]

    TRANSACTION_CODE_CHOICES = [
        ("22", "Credit"),
        ("23", "Prenote Credit"),
        ("27", "Debit"),
        ("28", "Prenote Debit"),
    ]

    pay_date = models.DateField()

    payment_type = models.CharField(
        max_length=3,
        choices=PAYMENT_TYPE_CHOICES
    )

    garnishment_type = models.CharField(
        max_length=100
    )

    medical_support_indicator = models.CharField(
        max_length=1,
        choices=MEDICAL_SUPPORT_CHOICES,
        default="N"
    )

    service_class_code = models.CharField(
        max_length=3,
        choices=SERVICE_CLASS_CODE_CHOICES
    )

    account_type = models.CharField(
        max_length=10,
        choices=ACCOUNT_TYPE_CHOICES
    )

    # Only required if account_type == "checking"
    transaction_code = models.CharField(
        max_length=2,
        choices=TRANSACTION_CODE_CHOICES,
        blank=True,
        null=True
    )

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_id} - {self.garnishment_type} ({self.pay_date})"
