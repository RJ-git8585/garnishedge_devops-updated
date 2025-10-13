from django.urls import path
from user_app.views import PEOAPI, PEOByIdAPI, PEOImportView, ExportPEODataView

app_name = 'peo'

urlpatterns = [
    path("details/", PEOAPI.as_view(), name="peo-list-create"),
    path("details/<int:pk>/", PEOByIdAPI.as_view(), name="peo-detail"),
    path("import/", PEOImportView.as_view(), name="peo-import"),
    path("export/", ExportPEODataView.as_view(), name="peo-export"),
]
