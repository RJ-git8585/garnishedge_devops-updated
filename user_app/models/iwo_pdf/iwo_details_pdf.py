from django.db import models

class IWOPDFFiles(models.Model):
    name = models.CharField(max_length=255)
    pdf_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "iwo_pdf_files"


