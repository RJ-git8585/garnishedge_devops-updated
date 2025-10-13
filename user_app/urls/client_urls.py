from django.urls import path
from user_app.views import ClientDetailsAPI, ClientImportView, ExportClientDataView

app_name = 'client'

urlpatterns = [
    path('details/', ClientDetailsAPI.as_view()),
    path('details/<int:pk>/', ClientDetailsAPI.as_view()),
    path('import/', ClientImportView.as_view(), name='client-import'),
    path('export/', ExportClientDataView.as_view(), name='client-export'),
]
