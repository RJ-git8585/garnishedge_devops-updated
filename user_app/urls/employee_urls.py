# app/urls/employee_urls.py
from django.urls import path
from user_app.views import (EmployeeDetailAPI,EmployeeDetailByIdAPI
    , EmployeeImportView,
     UpsertEmployeeDataView, ExportEmployeeDataView,EmployeeGarnishmentOrderCombineData)

app_name = 'employee'

urlpatterns = [

    #CRUD for the employee data
    path("details/", EmployeeDetailAPI.as_view(), name="employee-list-create"),
    path("details/<int:pk>/", EmployeeDetailByIdAPI.as_view(), name="employee-detail"),

    #Import employee using excel
    path('import/', EmployeeImportView.as_view(), name='import'),

    #Insert+Update Employee details using excel
    path('upsert/', UpsertEmployeeDataView.as_view(), name='upsert'),

    #Export employee data in excel
    path('export/', ExportEmployeeDataView.as_view(), name='export_employees'),

    #Get employee data 
    path('rules/', EmployeeGarnishmentOrderCombineData.as_view(), name='employee_rules'),
]
