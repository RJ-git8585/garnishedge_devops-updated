from django.urls import path
from processor.views.configs.exempt_views import ExemptRuleAPIView

app_name = 'exempt'

urlpatterns = [
    # Original URLs for backward compatibility (all garnishment types)
    path("rule/", ExemptRuleAPIView.as_view()),
    path("rule/<int:pk>/", ExemptRuleAPIView.as_view()),
    
    # New URLs with garnishment type filtering
    path("rule/<str:garnishment_type>/", ExemptRuleAPIView.as_view()),
    path("rule/<str:garnishment_type>/<int:pk>/", ExemptRuleAPIView.as_view()),
]


