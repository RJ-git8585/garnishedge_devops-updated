from django.urls import path
from user_app.views import PEOAPI, PEOByIdAPI

app_name = 'peo'

urlpatterns = [
    path("details/", PEOAPI.as_view(), name="peo-list-create"),
    path("details/<int:pk>/", PEOByIdAPI.as_view(), name="peo-detail"),
]
