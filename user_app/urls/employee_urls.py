# app/urls/employee_urls.py
from django.urls import path
from user_app.views import (EmployeeDetailsAPI,EmployeeDetailsByIdAPI
    , EmployeeImportView,
     UpsertEmployeeDataView, ExportEmployeeDataView,EmployeeGarnishmentOrderCombineData)
from user_app.views.employee_garnishment_views import (
    EmployeeGarnishmentDetailAPI,
    EmployeeGarnishmentUpdateAPI,
    EmployeeGarnishmentListAPI
)

app_name = 'employee'

urlpatterns = [

    #CRUD for the employee data
    path("details/", EmployeeDetailsAPI.as_view(), name="employee-list-create"),
    path("details/<int:pk>/", EmployeeDetailsByIdAPI.as_view(), name="employee-detail"),

    #Import employee using excel
    path('import/', EmployeeImportView.as_view(), name='import'),   

    #Insert+Update Employee details using excel
    path('upsert/', UpsertEmployeeDataView.as_view(), name='upsert'),

    #Export employee data in excel
    path('export/', ExportEmployeeDataView.as_view(), name='export_employees'),

    #Get employee data 
    path('rules/', EmployeeGarnishmentOrderCombineData.as_view(), name='employee_rules'),

    # New APIs for employee and garnishment order details
    path('garnishment-details/<str:ee_id>/<str:client_id>/', EmployeeGarnishmentDetailAPI.as_view(), name='employee-garnishment-details'),
    path('garnishment-update/<str:ee_id>/<str:client_id>/', EmployeeGarnishmentUpdateAPI.as_view(), name='employee-garnishment-update'),
    path('garnishment-list/', EmployeeGarnishmentListAPI.as_view(), name='employee-garnishment-list'),
]

