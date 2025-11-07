# app/urls/utility_urls.py
from django.urls import path

from user_app.views.utility_views import ( GarnishmentDashboardAPI
)

app_name = 'dashboard'

urlpatterns = [
    path('garnishment/', GarnishmentDashboardAPI.as_view(), name='garnishment_dashboard'),
]
