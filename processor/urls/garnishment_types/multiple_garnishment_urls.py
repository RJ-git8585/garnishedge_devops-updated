from django.urls import path
from processor.views.garnishment_types.multiple_garnishment_views import (
    MultipleGarnPriorityOrderAPIView,
    MultipleGarnPriorityOrderReorderAPIView
)

app_name = 'multiple_garnishment'

urlpatterns = [
    # MultipleGarnPriorityOrders CRUD endpoints
    path('priorities/', MultipleGarnPriorityOrderAPIView.as_view(), name='multiple_garn_priority_list_create'),
    path('priorities/<int:pk>/', MultipleGarnPriorityOrderAPIView.as_view(), name='multiple_garn_priority_detail'),
    path('priorities/reorder/', MultipleGarnPriorityOrderReorderAPIView.as_view(), name='multiple_garn_priority_reorder'),
]
