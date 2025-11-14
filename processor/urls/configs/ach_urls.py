from django.urls import path
from processor.views.configs.ach_views import (
    ACHFileGenerationView,
    ACHFileListView
)

app_name = 'ach'

urlpatterns = [
    # Generate ACH file - POST
    path("generate/", ACHFileGenerationView.as_view(), name="ach-generate"),
    
    # List generated ACH files - GET
    path("files/", ACHFileListView.as_view(), name="ach-files-list"),
]

