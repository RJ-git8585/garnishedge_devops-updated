from django.db import models

class IWODetailsPDF(models.Model):
    ee_id = models.ForeignKey('user_app.EmployeeDetail', on_delete=models.CASCADE, related_name="IWODetailsPDF",db_index=True)
    IWO_Status = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iwo_details_pdf"


