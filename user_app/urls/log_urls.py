from django.urls import path

from user_app.views.change_log_views import ChangeLogAPIView

app_name = "logs"

urlpatterns = [
    path("cdc/<int:user_id>/", ChangeLogAPIView.as_view(), name="cdc_logs"),
]

