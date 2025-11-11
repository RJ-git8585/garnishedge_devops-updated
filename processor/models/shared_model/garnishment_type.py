from django.db import models

class GarnishmentType(models.Model):
    code= models.CharField(max_length=10, blank =True, null=True)
    type = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    report_description= models.CharField(max_length=100,null=False)
    pay_stub_description= models.CharField(max_length=100,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.type

    class Meta:
        db_table = "garnishment_type"
        verbose_name ="garnishment_type"



