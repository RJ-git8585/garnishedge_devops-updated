"""
URL patterns for Payment History API endpoints.
"""
from django.urls import path
from processor.views.garnishment_types.payment_history_views import (
    PaymentHistoryListAPI,
    PaymentHistoryCreateAPI,
)

app_name = 'payment_history'

urlpatterns = [
    # List all payment history records
    path('list/', PaymentHistoryListAPI.as_view(), name='payment-history-list'),
    
    # Create payment history record
    path('create/', PaymentHistoryCreateAPI.as_view(), name='payment-history-create'),
]

