# app/urls/garnishment_urls.py
from django.urls import path
from processor.views import ChildSupportCalculationRules



app_name = 'child_support'

urlpatterns = [

    # Child support calculation rule
    path('rules/<str:state>/<str:employee_id>/<str:supports_2nd_family>/<str:arrears_of_more_than_12_weeks>/<str:de>/<int:no_of_order>/',
         ChildSupportCalculationRules.as_view(), name='calculation_rules')
         
]