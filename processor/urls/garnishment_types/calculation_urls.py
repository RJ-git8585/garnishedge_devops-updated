from django.urls import path

from processor.views.garnishment_types.calculation_views import PostCalculationView

app_name = 'garnishment'

urlpatterns = [


 # Garnishment calculation for api all types
    path('calculate/', PostCalculationView.as_view(), name='calculate')
    
    

]