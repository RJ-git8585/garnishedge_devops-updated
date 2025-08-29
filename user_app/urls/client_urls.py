from django.urls import path
from user_app.views import ClientDetailsAPI

app_name = 'client'

urlpatterns = [
    path('details/', ClientDetailsAPI.as_view()),
    path('details/<int:pk>/', ClientDetailsAPI.as_view()),
]
