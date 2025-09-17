# app/urls/garnishment_urls.py
from django.urls import path

from processor.views.garnishment_types.state_views import StateAPIView

app_name = 'state'

urlpatterns = [

    # CRUD for the state tax levy config
    path('details/',StateAPIView.as_view(), name='State'),
    path('<str:state>/',StateAPIView.as_view(), name='State'),

]
