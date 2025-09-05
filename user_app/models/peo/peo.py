from django.db import models
from user_app.utils import HashValue

class PEO(models.Model):
    state = models.ForeignKey('processor.State', on_delete=models.CASCADE, db_index=True,related_name="peos")
    peo_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=64)  # Store hashed value
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['peo_id']),
        ]

        db_table = "peo"

    def save(self, *args, **kwargs):
        if self.tax_id and len(self.tax_id) != 64:  # Avoid rehashing
            self.tax_id = HashValue.hash_value(self.tax_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name




