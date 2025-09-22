from django.urls import path
from user_app.views import BatchPayrollProcessingAPI

app_name = 'batch_processing'

urlpatterns = [
    path('payroll/batch/', BatchPayrollProcessingAPI.as_view(), name='batch-payroll-processing'),
]
