from django.urls import path
from processor.views.configs.ach_views import (
    ACHFileGenerationView,
    ACHFileListView,
    AchGarnishmentConfigListCreateAPIView,
    AchGarnishmentConfigDetailAPIView
)

app_name = 'ach'

urlpatterns = [
    # Generate ACH file - POST
    path("generate/", ACHFileGenerationView.as_view(), name="ach-generate"),
    
    # List generated ACH files - GET
    path("files/", ACHFileListView.as_view(), name="ach-files-list"),
    path("ach-configs/", AchGarnishmentConfigListCreateAPIView.as_view(), name="ach-config-list-create"),
    path("ach-configs/<int:pk>/", AchGarnishmentConfigDetailAPIView.as_view(), name="ach-config-detail"),
]

