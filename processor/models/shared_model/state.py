from django.db import models

class State(models.Model):
    state_code = models.CharField(max_length=100,unique=True)
    state = models.CharField(max_length=100, null=True, blank=True,db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table="state"
        verbose_name ="state"
