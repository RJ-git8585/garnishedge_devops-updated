from django.db import models

class PaymentHistory(models.Model):
    """Model to store payment history records for garnishment orders."""
    # case = models.ForeignKey('user_app.GarnishmentOrder',on_delete=models.CASCADE,related_name='payment_history',null=True,blank=True,help_text="Associated garnishment order"
    # )
    ee = models.ForeignKey('user_app.EmployeeDetail', on_delete=models.CASCADE, related_name="payment_history")
    case = models.ForeignKey('user_app.GarnishmentOrder', on_delete=models.CASCADE, related_name="payment_history")
    voucher_number = models.CharField(max_length=50, null=False, blank=False)
    pay_date = models.DateField(null=False, blank=False)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    paid_on = models.DateField(null=True, blank=True)
    check_number = models.CharField(max_length=50, null=True, blank=True)
    check_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ach_reference = models.CharField(max_length=255, null=True, blank=True)
    eft_check = models.DecimalField(max_digits=10,decimal_places=2,null=True, blank=True)
    comment = models.TextField(null=True, blank=True, help_text="Additional comments or notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.voucher_number} - {self.pay_date}"

    class Meta:
        db_table = "payment_history"
        verbose_name = "payment_history"
        verbose_name_plural = "payment_histories"
        ordering = ['-pay_date', '-created_at']
        indexes = [
            models.Index(fields=['ee']),
            models.Index(fields=['case']),
            models.Index(fields=['pay_date']),
            models.Index(fields=['voucher_number']),
        ]
    