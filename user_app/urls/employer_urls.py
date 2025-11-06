# app/urls/employer_urls.py
from django.urls import path
from user_app.views.employer_views import (
    EmployerDetails
)

app_name = 'user'

urlpatterns = [

    # CRUD
    path('details/', EmployerDetails.as_view(), name='details'),
    path('details/<int:id>/', EmployerDetails.as_view(), name='details'),

]
