"""
API views for Payment History management.
"""
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db.models import Sum, DecimalField, Case, When, Value
from django.db.models.functions import Coalesce

from processor.models.payment_history import PaymentHistory
from user_app.models import GarnishmentOrder, EmployeeDetail
from processor.serializers.payment_history_serializers import (
    PaymentHistorySerializer,
    PaymentHistoryCreateSerializer,
    PaymentHistorySummarySerializer,
    PaymentHistoryListResponseSerializer,
)
from processor.garnishment_library.utils.response import ResponseHelper
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


class PaymentHistoryListAPI(APIView):
    """
    API to retrieve all payment history records with summary statistics.
    
    Returns:
    - List of all payment history records with employee and case information
    - Summary: paid_to_date (sum of amount_due), total_garnishment, total_eft
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        responses={
            200: PaymentHistoryListResponseSerializer,
        },
        operation_summary="Get all payment history with summary",
        operation_description="Retrieve all payment history records from the database with summary statistics including paid to date amount."
    )
    def get(self, request):
        """Get all payment history records with summary statistics."""
        # Get all payment history records with related employee and case data
        payments = PaymentHistory.objects.select_related('ee', 'case').order_by('-pay_date', '-created_at')
        
        # Calculate summary statistics
        # Paid to Date: Sum of all amount_due
        paid_to_date_result = payments.aggregate(
            total=Coalesce(
                Sum('amount_due', output_field=DecimalField(max_digits=12, decimal_places=2)), 
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        paid_to_date = paid_to_date_result['total'] or 0
        
        # Total Garnishment: Sum of total_amount_owed from all unique cases
        # Get unique cases and sum their total_amount_owed
        unique_cases = payments.values_list('case', flat=True).distinct()
        if unique_cases:
            total_garnishment_result = GarnishmentOrder.objects.filter(
                id__in=unique_cases
            ).aggregate(
                total=Coalesce(
                    Sum('total_amount_owed', output_field=DecimalField(max_digits=12, decimal_places=2)), 
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
            total_garnishment = total_garnishment_result['total'] or 0
        else:
            total_garnishment = 0
        
        # Total EFT: Sum of check_amount or eft_check (prefer check_amount)
        total_eft_result = payments.aggregate(
            total=Coalesce(
                Sum(
                    Case(
                        When(check_amount__isnull=False, then='check_amount'),
                        default='eft_check',
                        output_field=DecimalField(max_digits=10, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        total_eft = total_eft_result['total'] or 0
        
        # Serialize the data
        summary_data = {
            'paid_to_date': paid_to_date,
            'total_garnishment': total_garnishment,
            'total_eft': total_eft,
        }
        
        summary_serializer = PaymentHistorySummarySerializer(summary_data)
        payments_serializer = PaymentHistorySerializer(payments, many=True)
        
        response_data = {
            'summary': summary_serializer.data,
            'payments': payments_serializer.data,
        }
        
        return ResponseHelper.success_response(
            data=response_data,
            message="Payment history retrieved successfully"
        )


class PaymentHistoryCreateAPI(APIView):
    """
    API to create a new payment history entry.
    
    This endpoint creates a new payment record in the payment history table.
    Voucher number is auto-generated as a 6-digit sequential number.
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        request_body=PaymentHistoryCreateSerializer,
        responses={
            201: PaymentHistorySerializer,
            400: 'Bad Request - Validation error',
            404: 'Employee or Garnishment order not found',
        },
        operation_summary="Create payment history",
        operation_description="Create a new payment history record. Voucher number is auto-generated as a 6-digit sequential number."
    )
    def post(self, request):
        """Create a new payment history record."""
        serializer = PaymentHistoryCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return ResponseHelper.error_response(
                message="Validation error",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        ee_id = validated_data.pop('ee_id')
        case_id = validated_data.pop('case_id')
        
        try:
            # Get the employee
            employee = EmployeeDetail.objects.get(ee_id=ee_id)
        except EmployeeDetail.DoesNotExist:
            return ResponseHelper.error_response(
                message=f"Employee with ee_id '{ee_id}' not found",
                error=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Get the garnishment order
            order = GarnishmentOrder.objects.get(case_id=case_id)
        except GarnishmentOrder.DoesNotExist:
            return ResponseHelper.error_response(
                message=f"Garnishment order with case_id '{case_id}' not found",
                error=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Generate 6-digit sequential voucher number (000001, 000002, etc.)
        # Get the maximum existing voucher number that is a pure 6-digit number
        existing_vouchers = PaymentHistory.objects.values_list('voucher_number', flat=True)
        max_number = 0
        
        for voucher in existing_vouchers:
            if voucher and len(str(voucher)) == 6 and str(voucher).isdigit():
                try:
                    num = int(voucher)
                    if 0 <= num <= 999999:
                        max_number = max(max_number, num)
                except ValueError:
                    continue
        
        # Increment to get next sequential number
        next_number = max_number + 1
        
        # If we've reached the maximum, wrap around to 1 (or you can raise an error)
        if next_number > 999999:
            next_number = 1
        
        # Format as 6-digit number with leading zeros (e.g., 000001, 000002, etc.)
        voucher_number = f"{next_number:06d}"
        
        # Ensure voucher number is unique (in case of wrap-around, find next available)
        while PaymentHistory.objects.filter(voucher_number=voucher_number).exists():
            next_number = (next_number + 1) % 1000000
            if next_number == 0:
                next_number = 1  # Skip 000000
            voucher_number = f"{next_number:06d}"
        
        # Create the payment history record
        payment = PaymentHistory.objects.create(
            ee=employee,
            case=order,
            voucher_number=voucher_number,
            **validated_data
        )
        
        payment_serializer = PaymentHistorySerializer(payment)
        
        return ResponseHelper.success_response(
            data=payment_serializer.data,
            message="Payment history created successfully",
            status_code=status.HTTP_201_CREATED
        )



