from django.db import models

class DeductionPriority(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, related_name="priority_state",db_index=True)
    deduction_type = models.ForeignKey('processor.deductions', on_delete=models.CASCADE, related_name="priority_deduction_type",db_index=True)
    priority_order = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = "child_support_priority"
        verbose_name= "child_support_priority"


