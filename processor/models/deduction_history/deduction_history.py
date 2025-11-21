from django.db import models

class DeductionHistory(models.Model):
    """Model to store deduction history records for garnishment orders."""
    
    case = models.ForeignKey(
        'user_app.GarnishmentOrder', 
        on_delete=models.CASCADE, 
        related_name="deduction_history",
        help_text="Associated garnishment order"
    )
    voucher_number = models.CharField(max_length=50, null=False, blank=False, help_text="Voucher number")
    pay_date = models.DateField(null=False, blank=False, help_text="Pay date")
    deduction_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=False, 
        blank=False,
        help_text="Deduction amount"
    )
    paid_on = models.DateField(null=True, blank=True, help_text="Date when payment was made")
    check_number = models.CharField(max_length=50, null=True, blank=True, help_text="Check number")
    ach_reference = models.CharField(max_length=255, null=True, blank=True, help_text="ACH reference number")
    payment_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Payment amount"
    )
    void_check = models.BooleanField(default=False, help_text="Whether the check is void")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Deduction {self.voucher_number} - {self.pay_date}"

    class Meta:
        db_table = "deduction_history"
        verbose_name = "deduction_history"
        verbose_name_plural = "deduction_histories"
        ordering = ['-pay_date', '-created_at']
        indexes = [
            models.Index(fields=['case']),
            models.Index(fields=['pay_date']),
            models.Index(fields=['voucher_number']),
            models.Index(fields=['void_check']),
        ]

