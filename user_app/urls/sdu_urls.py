from django.urls import path
from user_app.views.sdu_views import SDUByIDAPIView, SDUByStateAPIView, SDUImportView, ExportSDUDataView

app_name = 'sdu'

urlpatterns = [
    # CRUD by id
    path('details/', SDUByIDAPIView.as_view(), name='detail'),
    path('details/<int:id>/', SDUByIDAPIView.as_view(), name='sdu-by-id'),
    # Get SDUs by state name or abbreviation 
    path('state/<str:state>/', SDUByStateAPIView.as_view(), name='sdu-by-state'),
    # Import/Upsert SDUs from file
    path('import/', SDUImportView.as_view(), name='sdu-import'),
    # Export SDUs to Excel
    path('export/', ExportSDUDataView.as_view(), name='sdu-export'),
]
