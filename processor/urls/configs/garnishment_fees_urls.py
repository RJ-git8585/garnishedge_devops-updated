# app/urls/employer_urls.py
from django.urls import path
from processor.views import (
    GarnishmentFeesRules
)

app_name = 'garnishment_fees'

urlpatterns = [

  #CRUD for the Garnishment fees rules
  path('rules/<str:rule>/',
       GarnishmentFeesRules.as_view(), name='fees_rules'),
  path('rules/', GarnishmentFeesRules.as_view(), name='fees_rules'),


]
