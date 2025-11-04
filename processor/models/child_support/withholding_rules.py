from django.db import models

class WithholdingRules(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True)
    rule = models.IntegerField()
    allocation_method = models.CharField(max_length=255)
    withholding_limit = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "withholding_rules"

