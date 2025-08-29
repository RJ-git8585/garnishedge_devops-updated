from django.urls import path
from processor.views import ExemptConfigAPIView

app_name = 'exempt_amt'

urlpatterns = [
    path("config/", ExemptConfigAPIView.as_view()),
    path("config/<int:pk>/", ExemptConfigAPIView.as_view()),
]
