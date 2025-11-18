from django.db import models

class EmplopyeeAddress(models.Model):
    ee= models.OneToOneField('user_app.EmployeeDetail', on_delete=models.CASCADE, related_name="employee_addresses")
    address_1=models.TextField(max_length=255,blank=True, null=True)
    address_2=models.TextField(max_length=255,blank=True, null=True)
    zip_code=models.IntegerField(null=False)
    geo_code=models.IntegerField(null=False)
    city=models.CharField(max_length=100,null=False)
    state=models.CharField(max_length=100,null=False)
    county=models.CharField(max_length=100,blank=True, null=True)
    country=models.CharField(max_length=100,null=False)

    class Meta:
        indexes = [
            models.Index(fields=['ee'])
        ]
        db_table = "employee_address"

    