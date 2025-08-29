# app/urls/garnishment_urls.py
from django.urls import path
from user_app.views.iwo_pdf_views import (
    InsertIWODetailView, ConvertExcelToJsonView, PDFUploadView, GETIWOPDFData
)


app_name = 'iwo_pdf'

urlpatterns = [
    path('iwo-data/', InsertIWODetailView.as_view(), name='iwo_data'),

    # Excel to JSON convert API
    path('convert-excel/', ConvertExcelToJsonView.as_view(), name='convert_excel'),

    # PDF Data
    path('upload-pdf/', PDFUploadView.as_view(), name='upload_pdf'),
    path('get-pdf-data/', GETIWOPDFData.as_view(), name='get_pdf_data')

]
