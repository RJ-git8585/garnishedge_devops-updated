from django.db import models

class IWODetailsPDF(models.Model):
    IWO_ID = models.AutoField(primary_key=True)
    ee_id = models.ForeignKey('user_app.EmployeeDetails', on_delete=models.CASCADE, related_name="IWODetailsPDF")
    IWO_Status = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iwo_details_pdf"


