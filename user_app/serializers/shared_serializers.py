
from rest_framework import serializers
from user_app.models import IWOPDFFiles

class IWOPDFFilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = IWOPDFFiles
        fields = ['id', 'name', 'pdf_url', 'uploaded_at']

