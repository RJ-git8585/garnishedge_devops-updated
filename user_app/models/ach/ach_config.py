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
        # Checking account codes
        ("22", "Credit"),  # Credit to checking account
        ("23", "Prenote Credit"),  # Prenote credit to checking account
        ("27", "Debit"),  # Debit to checking account
        ("28", "Prenote Debit"),  # Prenote debit to checking account
        # Savings account codes
        ("32", "Credit"),  # Credit to savings account
        ("33", "Prenote Credit"),  # Prenote credit to savings account
        ("37", "Debit"),  # Debit to savings account
        ("38", "Prenote Debit"),  # Prenote debit to savings account
    ]

    payment_type = models.CharField(
        max_length=3,
        choices=PAYMENT_TYPE_CHOICES
    )


    medical_support_indicator = models.CharField(
        max_length=1,
        choices=MEDICAL_SUPPORT_CHOICES,
        default="N"
    )

    company_name=models.CharField(
        max_length=255
    )

    company_id = models.CharField(
        max_length=20
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

    # PEOs Bank Routing number (Wells Fargo) - Immediate destination
    peos_bank_routing_number = models.CharField(
        max_length=50,
        help_text="PEOs Bank Routing number (Wells Fargo) - Immediate destination"
    )

    peos_bank_name = models.CharField(
        max_length=255,
        default="Wells Fargo Garnishment"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_id} - {self.company_name} ({self.payment_type})"

    class meta:
        db_table= 'ach_config'



