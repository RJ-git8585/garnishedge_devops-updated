# app/urls/utility_urls.py
from django.urls import path

from user_app.views.utility_views import (
    get_dashboard_data,
    GarnishmentDashboardAPI
)

app_name = 'dashboard'

urlpatterns = [
    path('dashboard/', get_dashboard_data, name='dashboard'),
    path('garnishment/', GarnishmentDashboardAPI.as_view(), name='garnishment_dashboard'),
]
