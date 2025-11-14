from django.urls import path
from processor.views.garnishment_types.garnishment_type_views import GarnishmentTypeAPIView, GarnishmentTypeCodeAPIView

app_name = 'garnishment_type'

urlpatterns = [
    # CRUD operations
    path('details/', GarnishmentTypeAPIView.as_view(), name='garnishment-type-list-create'),
    path('details/<int:pk>/', GarnishmentTypeAPIView.as_view(), name='garnishment-type-detail-update-delete'),
    # Code-only endpoint
    path('codes/', GarnishmentTypeCodeAPIView.as_view(), name='garnishment-type-codes'),
]

