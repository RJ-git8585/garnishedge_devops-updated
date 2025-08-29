from django.db import models

class DisposableEarningState(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="DEState",db_index=True)
    payroll = models.ForeignKey('user_app.Payroll', on_delete=models.CASCADE, related_name="DEState")
    disposable_earnings = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = "de_state_rules"
        verbose_name= "de_state_rules"