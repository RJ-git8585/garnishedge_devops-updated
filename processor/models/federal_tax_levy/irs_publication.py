from django.db import models

class IRSPublication(models.Model):
    year =  models.IntegerField(null=True, blank=True,db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "irs_publication_1494"
        verbose_name = "irs_publication_1494"
