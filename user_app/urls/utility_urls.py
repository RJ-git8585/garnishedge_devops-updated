# app/urls/utility_urls.py
from django.urls import path

from user_app.views.utility_views import (
    get_dashboard_data
)

app_name = 'utility'

urlpatterns = [
    path('dashboard/', get_dashboard_data, name='dashboard'),
]
