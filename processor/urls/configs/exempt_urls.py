from django.urls import path
from processor.views.configs.exempt_views import ExemptConfigAPIView

app_name = 'exempt_amt'

urlpatterns = [
    # Original URLs for backward compatibility (all garnishment types)
    path("config/", ExemptConfigAPIView.as_view()),
    path("config/<int:pk>/", ExemptConfigAPIView.as_view()),
    
    # New URLs with garnishment type filtering
    path("config/<str:garnishment_type>/", ExemptConfigAPIView.as_view()),
    path("config/<str:garnishment_type>/<int:pk>/", ExemptConfigAPIView.as_view()),
    
    # URL for getting by rule_id (GET only - use this URL pattern)
    # For PUT/DELETE, use the pk-based URLs above
    path("config/<str:garnishment_type>/rule/<int:rule_id>/", ExemptConfigAPIView.as_view()),
]

