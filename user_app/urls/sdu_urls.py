from django.urls import path
from user_app.views.payee_views import PayeeByIDAPIView, PayeeByStateAPIView, PayeeImportView, ExportPayeeDataView

app_name = 'sdu'

urlpatterns = [
    # CRUD by id
    path('details/', PayeeByIDAPIView.as_view(), name='detail'),
    path('details/<int:id>/', PayeeByIDAPIView.as_view(), name='sdu-by-id'),
    # Get SDUs by state name or abbreviation 
    path('state/<str:state>/', PayeeByStateAPIView.as_view(), name='sdu-by-state'),
    # Import/Upsert SDUs from file
    path('import/', PayeeImportView.as_view(), name='sdu-import'),
    # Export SDUs to Excel
    path('export/', ExportPayeeDataView.as_view(), name='sdu-export'),
]
