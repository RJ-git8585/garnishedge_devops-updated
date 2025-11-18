from django.db import models

class PayeeDetails(models.Model):
    """
    State Disbursement Unit - where child support or garnishment payments are sent.
    """

    # Primary key for the payee record (renamed from payee_id to id)
    id = models.AutoField(primary_key=True)
    payee_id = models.CharField(max_length=255, unique=True)
    payee_type = models.CharField(max_length=100)
    payee = models.CharField(max_length=255)
    routing_number = models.CharField(max_length=20, blank=True, null=True)
    bank_account = models.CharField(max_length=50, blank=True, null=True)
    case_number_required = models.BooleanField(default=False)
    case_number_format = models.CharField(max_length=100, blank=True, null=True)
    fips_required = models.BooleanField(default=False)
    fips_length = models.IntegerField(blank=True, null=True)
    last_used = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    # Link this payee to a specific garnishment order (case)
    # State is now stored as a ForeignKey for better normalization
    state = models.ForeignKey(
        'processor.State',
        on_delete=models.CASCADE,
        related_name="sdus",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payee_details'

        indexes = [
            models.Index(fields=["id"]),
            models.Index(fields=["payee_id"]),
        ]


    def __str__(self):
        return self.payee
