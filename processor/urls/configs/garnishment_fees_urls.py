# app/urls/employer_urls.py
from django.urls import path
from processor.views import (
    GarnishmentFeesCreateAPI,GarnishmentFeesListByFilterAPI,GarnishmentFeesDetailAPI
)

app_name = 'garnishment_fees'


urlpatterns = [
    # Create new fee
    path("rules/", GarnishmentFeesCreateAPI.as_view(), name="garnishment-fees-create"),

    # Filter by state, pay_period, garnishment_type
    path(
        "rules/filter/<str:state>/<str:pay_period>/<str:garnishment_type_name>/",
        GarnishmentFeesListByFilterAPI.as_view(),
        name="garnishment-fees-filter",
    ),

    # Retrieve, Update, Delete by id
    path(
        "rules/<int:pk>/",
        GarnishmentFeesDetailAPI.as_view(),
        name="garnishment-fees-detail",
    ),
]