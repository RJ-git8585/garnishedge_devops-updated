# app/urls/employer_urls.py
from django.urls import path
from processor.views.configs.garnishment_fees_views import (
    GarnishmentFeesAPIView,
    GarnishmentFeesListByFilterAPI
)

app_name = 'garnishment_fees'


urlpatterns = [
    # CRUD operations - GET (list all), POST (create)
    path("details/", GarnishmentFeesAPIView.as_view(), name="garnishment-fees-list-create"),
    
    # CRUD operations - GET (retrieve), PUT (update), DELETE (delete) by id
    path(
        "details/<int:pk>/",
        GarnishmentFeesAPIView.as_view(),
        name="garnishment-fees-detail",
    ),
    
    # Filter by state, pay_period, garnishment_type
    path(
        "details/filter/<str:state>/<str:pay_period>/<str:garnishment_type_name>/",
        GarnishmentFeesListByFilterAPI.as_view(),
        name="garnishment-fees-filter",
    ),


]