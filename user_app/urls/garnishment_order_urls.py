# app/urls/employer_urls.py
from django.urls import path
from user_app.views.employer_views import (
    EmployerDetails
)
from user_app.views.garnishment_order_views import GarnishmentOrderDetails,UpsertGarnishmentOrderView,GarnishmentOrderAPI,GarnishmentOrderDetailAPI,ExportGarnishmentOrderDataView,GarnishmentOrderImportView

app_name = 'order'

urlpatterns = [

    path('details/', GarnishmentOrderAPI.as_view(), name='garnishment-order-list-create'),
    path('details/<int:id>/', GarnishmentOrderDetailAPI.as_view(), name='garnishment-order-detail'),

    # CRUD for the garnishment order
    path('order-details/', GarnishmentOrderDetails.as_view(), name='order_details'),
    path('order-details/<str:case_id>/',
         GarnishmentOrderDetails.as_view(), name='delete_order'),

    # Import Order using excel
    path('import/', GarnishmentOrderImportView.as_view(), name='import_orders'),


    # Insert+Update order details using excel
    path('upsert/', UpsertGarnishmentOrderView.as_view(), name='upsert_orders'),

    # Export garnishment order data in excel
    path('export/', ExportGarnishmentOrderDataView.as_view(),
         name='export_orders'),

]

