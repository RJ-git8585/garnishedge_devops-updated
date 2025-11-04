from rest_framework.views import APIView
from rest_framework import status
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from processor.garnishment_library.utils.response import ResponseHelper
from rest_framework.parsers import MultiPartParser, FormParser
from user_app.models import GarnishmentOrder
from user_app.serializers import GarnishmentOrderSerializer
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from io import BytesIO
import pandas as pd
import math
import csv
from rest_framework.response import Response
from rest_framework.views import APIView
from user_app.models import GarnishmentOrder
from datetime import datetime
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR
)
from rest_framework.permissions import AllowAny
from processor.garnishment_library import PaginationHelper
from user_app.utils import DataProcessingUtils
from django.core.paginator import Paginator, EmptyPage

class GarnishmentOrderImportView(APIView):
    """
    API view to handle the import of garnishment orders from a file.
    Optimized for bulk processing with minimal database queries.
    """
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Excel file to upload"
            ),
            openapi.Parameter(
                name='title',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Optional title"
            )
        ],
        responses={
            201: 'File processed successfully',
            400: 'No file provided or unsupported file format',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            if 'file' not in request.FILES:
                return ResponseHelper.error_response(
                    message="No file provided",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES['file']
            file_name = file.name

            # Read file based on extension
            if file_name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file_name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb', '.odf', '.ods', '.odt')):
                df = pd.read_excel(file)
            else:
                return ResponseHelper.error_response(
                    message="Unsupported file format. Please upload a CSV or Excel file.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Normalize column names
            df.rename(columns=lambda c: DataProcessingUtils.normalize_field_name(c), inplace=True)
            
            # Process data in batches for better performance
            batch_size = 200
            added_orders = []
            updated_orders = []
            validation_errors = []
            
            # Pre-fetch existing orders to avoid repeated queries
            existing_case_ids = set(GarnishmentOrder.objects.values_list('case_id', flat=True))
            
            # Pre-fetch all foreign key mappings to avoid repeated queries
            from user_app.models import EmployeeDetail
            from processor.models import State, GarnishmentType
            
            employee_mapping = {emp.ee_id: emp.id for emp in EmployeeDetail.objects.all()}
            employee_ssn_mapping = {str(emp.ssn).strip(): emp.id for emp in EmployeeDetail.objects.exclude(ssn__isnull=True).exclude(ssn='')}
            # Create case-insensitive mappings for state and garnishment type
            state_mapping = {(s.state or '').lower(): s.id for s in State.objects.all()}
            garnishment_type_mapping = {(gt.type or '').lower(): gt.id for gt in GarnishmentType.objects.all()}
            
            # Process data in batches
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                
                batch_orders_to_create = []
                batch_orders_to_update = []
                
                for _, row in batch_df.iterrows():
                    try:
                        # Process row data efficiently
                        order_data = self._process_order_row(row)
                        
                        if not order_data:
                            validation_errors.append(f"Row {batch_start + _ + 1}: No order data after processing")
                            continue
                            
                        case_id = order_data.get("case_id")
                        if not case_id:
                            validation_errors.append(f"Row {batch_start + _ + 1}: Missing case_id")
                            continue
                        
                        # Check if order exists
                        if case_id in existing_case_ids:
                            # Prepare for update
                            batch_orders_to_update.append((case_id, order_data))
                            updated_orders.append(case_id)
                        else:
                            # Prepare for creation
                            batch_orders_to_create.append(order_data)
                            
                    except Exception as row_e:
                        validation_errors.append(f"Row {batch_start + _ + 1}: {str(row_e)}")
                        continue
                
                # Bulk create new orders
                if batch_orders_to_create:
                    created_case_ids, skip_reasons = self._bulk_create_orders(batch_orders_to_create, employee_mapping, employee_ssn_mapping, state_mapping, garnishment_type_mapping)
                    added_orders.extend(created_case_ids)
                    validation_errors.extend(skip_reasons[:20])  # Add first 20 detailed skip reasons
                    # Update existing_case_ids set to include newly created orders
                    existing_case_ids.update(created_case_ids)
                
                # Bulk update existing orders
                if batch_orders_to_update:
                    self._bulk_update_orders(batch_orders_to_update, employee_mapping, state_mapping, garnishment_type_mapping)
            
            # Build response data
            response_data = {
                "added_count": len(added_orders),
                "updated_count": len(updated_orders),
                "validation_errors_count": len(validation_errors)
            }
            
            if added_orders:
                response_data["added_orders"] = added_orders[:200]  # Limit response size to prevent huge responses
                if len(added_orders) > 200:
                    response_data["added_orders_truncated"] = True
            
            if updated_orders:
                response_data["updated_orders"] = updated_orders[:200]  # Limit response size to prevent huge responses
                if len(updated_orders) > 200:
                    response_data["updated_orders_truncated"] = True
            
            if validation_errors:
                response_data["validation_errors"] = validation_errors[:20]  # Limit error details
                if len(validation_errors) > 20:
                    response_data["validation_errors_truncated"] = True
            
            # If no records were added or updated
            if not added_orders and not updated_orders:
                # If there are validation errors, return 400 Bad Request
                if validation_errors:
                    return ResponseHelper.error_response(
                        message="No valid data to process. All records failed validation.",
                        error=response_data,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # No data and no errors - could be empty file or all duplicate
                    return ResponseHelper.success_response(
                        message="No valid data to process",
                        data=response_data,
                        status_code=status.HTTP_200_OK
                    )

            # If some records succeeded but there were also validation errors
            if validation_errors:
                return ResponseHelper.success_response(
                    message="File processed with some errors",
                    data=response_data,
                    status_code=status.HTTP_201_CREATED
                )

            # All records succeeded without errors
            return ResponseHelper.success_response(
                message="File processed successfully",
                data=response_data,
                status_code=status.HTTP_201_CREATED
            )

        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to import garnishment orders",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_order_row(self, row):
        """Process a single order row efficiently."""
        try:
            # Normalize column names first
            normalized_row = {}
            for key, value in row.items():
                if key and not str(key).startswith('Unnamed'):
                    normalized_key = DataProcessingUtils.normalize_field_name(key)
                    normalized_row[normalized_key] = value
                else:
                    normalized_row[key] = value
            
            # Define date fields that need parsing
            date_fields = [
                "override_start_date", "override_stop_date", "paid_till_date",
                "issued_date", "received_date", "start_date", "stop_date"
            ]
            
            order_data = {
                EE.CASE_ID: normalized_row.get(EE.CASE_ID),
                "ssn": normalized_row.get("ssn"),
                "issuing_state": normalized_row.get("issuing_state"),
                "garnishment_type": normalized_row.get("garnishment_type"),
                "garnishment_fees": normalized_row.get("garnishment_fees"),
                "payee": normalized_row.get("payee"),
                "override_amount": normalized_row.get("override_amount"),
                "is_consumer_debt": normalized_row.get("is_consumer_debt"),
                "ordered_amount": normalized_row.get("ordered_amount"),
                "garnishing_authority": normalized_row.get("garnishing_authority"),
                "withholding_amount": normalized_row.get("withholding_amount"),
                "current_child_support": normalized_row.get("current_child_support"),
                "current_medical_support": normalized_row.get("current_medical_support"),
                "child_support_arrear": normalized_row.get("child_support_arrear"),
                "medical_support_arrear": normalized_row.get("medical_support_arrear"),
                "current_spousal_support": normalized_row.get("current_spousal_support"),
                "spousal_support_arrear": normalized_row.get("spousal_support_arrear"),
                "fips_code": normalized_row.get("fips_code"),
                "arrear_greater_than_12_weeks": normalized_row.get("arrear_greater_than_12_weeks"),
                "arrear_amount": normalized_row.get("arrear_amount"),
            }
            # Parse date fields using the utility function
            for date_field in date_fields:
                order_data[date_field] = DataProcessingUtils.parse_date_field(normalized_row.get(date_field))
                    
            # Clean and normalize data
            order_data = DataProcessingUtils.clean_data_row(order_data)
            
            return order_data
            
        except Exception as e:
            raise Exception(f"Error processing row: {str(e)}")
    
    def _bulk_create_orders(self, orders_data, employee_mapping, employee_ssn_mapping, state_mapping, garnishment_type_mapping):
        """Bulk create orders using bulk_create for better performance. Returns tuple of (created_case_ids, skip_reasons)."""
        if not orders_data:
            return [], []
            
        created_case_ids = []
        skip_reasons = []
        try:
            from django.db import transaction
            
            with transaction.atomic():
                # Prepare bulk insert data
                bulk_orders = []
                for order_data in orders_data:
                    try:

                        ssn = order_data.get("ssn")
                        issuing_state = order_data.get("issuing_state")
                        garnishment_type = order_data.get("garnishment_type")
                        case_id = order_data.get("case_id")
                        
                        # Find employee by SSN
                        employee_id = None
                        if ssn:
                            key = str(ssn).strip()
                            employee_id = employee_ssn_mapping.get(key)
                        
                        if not employee_id:
                            skip_reasons.append(f"case_id={case_id}: No employee found for ssn={ssn or 'N/A'}")
                            continue  # Skip if no valid employee found
                        
                        # Validate required foreign keys (case-insensitive)
                        issuing_state_id = state_mapping.get((issuing_state or '').lower())
                        
                        # Map garnishment type with variant handling
                        garnishment_type_lower = (garnishment_type or '').lower()
                        # Handle variant names
                        garnishment_type_variants = {
                            'ftb_order': 'franchise_tax_board',
                            'ftborder': 'franchise_tax_board',
                        }
                        garnishment_type_normalized = garnishment_type_variants.get(garnishment_type_lower, garnishment_type_lower)
                        garnishment_type_id = garnishment_type_mapping.get(garnishment_type_normalized)
                        
                        if not issuing_state_id:
                            skip_reasons.append(f"case_id={case_id}: Invalid issuing_state='{issuing_state or 'N/A'}'. Available: {list(state_mapping.keys())[:5]}")
                            continue  # Skip if issuing_state is missing or invalid
                        if not garnishment_type_id:
                            skip_reasons.append(f"case_id={case_id}: Invalid garnishment_type='{garnishment_type or 'N/A'}'. Available: {list(garnishment_type_mapping.keys())[:5]}")
                            continue  # Skip if garnishment_type is missing or invalid
                        
                        bulk_orders.append(GarnishmentOrder(
                            case_id=case_id,
                            employee_id=employee_id,
                            issuing_state_id=issuing_state_id,
                            garnishment_type_id=garnishment_type_id,
                            is_consumer_debt=order_data.get("is_consumer_debt", False),
                            issued_date=order_data.get("issued_date"),
                            received_date=order_data.get("received_date"),
                            start_date=order_data.get("start_date"),
                            stop_date=order_data.get("stop_date"),
                            deduction_code=order_data.get("deduction_code", ""),
                            ordered_amount=order_data.get("ordered_amount", 0.00),
                            fein=order_data.get("fein", ""),
                            garnishing_authority=order_data.get("garnishing_authority"),
                            withholding_amount=order_data.get("withholding_amount", 0.00),
                            garnishment_fees=order_data.get("garnishment_fees", 0.00),
                            fips_code=order_data.get("fips_code"),
                            payee=order_data.get("payee"),
                            override_amount=order_data.get("override_amount"),
                            override_start_date=order_data.get("override_start_date"),
                            override_stop_date=order_data.get("override_stop_date"),
                            paid_till_date=order_data.get("paid_till_date"),
                            arrear_greater_than_12_weeks=order_data.get("arrear_greater_than_12_weeks", False),
                            arrear_amount=order_data.get("arrear_amount"),
                            current_child_support=order_data.get("current_child_support"),
                            current_medical_support=order_data.get("current_medical_support"),
                            current_spousal_support=order_data.get("current_spousal_support"),
                            medical_support_arrear=order_data.get("medical_support_arrear"),
                            child_support_arrear=order_data.get("child_support_arrear"),
                            spousal_support_arrear=order_data.get("spousal_support_arrear"),
                        ))
                        created_case_ids.append(case_id)
                    except Exception as e:
                        skip_reasons.append(f"case_id={case_id or 'N/A'}: Exception - {str(e)}")
                        continue  # Skip problematic records
                
                # Bulk create
                if bulk_orders:
                    GarnishmentOrder.objects.bulk_create(bulk_orders, ignore_conflicts=True)
                
                return created_case_ids, skip_reasons

        except Exception as e:
            raise Exception(f"Bulk create failed: {str(e)}")
    
    def _bulk_update_orders(self, orders_data, employee_mapping, state_mapping, garnishment_type_mapping):
        """Bulk update orders efficiently."""
        if not orders_data:
            return
            
        try:
            from django.db import transaction
            
            with transaction.atomic():
                # Get existing orders
                case_ids = [order[0] for order in orders_data]
                existing_orders = {
                    order.case_id: order for order in GarnishmentOrder.objects.filter(case_id__in=case_ids)
                }
                
                orders_to_update = []
                for case_id, order_data in orders_data:
                    if case_id in existing_orders:
                        order = existing_orders[case_id]
                        
                        # Update fields
                        order.is_consumer_debt = order_data.get("is_consumer_debt", order.is_consumer_debt)
                        order.issued_date = order_data.get("issued_date", order.issued_date)
                        order.received_date = order_data.get("received_date", order.received_date)
                        order.start_date = order_data.get("start_date", order.start_date)
                        order.stop_date = order_data.get("stop_date", order.stop_date)
                        order.deduction_code = order_data.get("deduction_code", order.deduction_code)
                        order.ordered_amount = order_data.get("ordered_amount", order.ordered_amount)
                        order.fein = order_data.get("fein", order.fein)
                        order.garnishing_authority = order_data.get("garnishing_authority", order.garnishing_authority)
                        order.withholding_amount = order_data.get("withholding_amount", order.withholding_amount)
                        order.garnishment_fees = order_data.get("garnishment_fees", order.garnishment_fees)
                        order.fips_code = order_data.get("fips_code", order.fips_code)
                        order.payee = order_data.get("payee", order.payee)
                        order.override_amount = order_data.get("override_amount", order.override_amount)
                        order.override_start_date = order_data.get("override_start_date", order.override_start_date)
                        order.override_stop_date = order_data.get("override_stop_date", order.override_stop_date)
                        order.paid_till_date = order_data.get("paid_till_date", order.paid_till_date)
                        order.arrear_greater_than_12_weeks = order_data.get("arrear_greater_than_12_weeks", order.arrear_greater_than_12_weeks)
                        order.arrear_amount = order_data.get("arrear_amount", order.arrear_amount)
                        order.current_child_support = order_data.get("current_child_support", order.current_child_support)
                        order.current_medical_support = order_data.get("current_medical_support", order.current_medical_support)
                        order.current_spousal_support = order_data.get("current_spousal_support", order.current_spousal_support)
                        order.medical_support_arrear = order_data.get("medical_support_arrear", order.medical_support_arrear)
                        order.child_support_arrear = order_data.get("child_support_arrear", order.child_support_arrear)
                        order.spousal_support_arrear = order_data.get("spousal_support_arrear", order.spousal_support_arrear)
                        
                        # Update foreign keys if provided
                        if order_data.get("issuing_state") and order_data.get("issuing_state") in state_mapping:
                            order.issuing_state_id = state_mapping[order_data.get("issuing_state")]
                        if order_data.get("garnishment_type") and order_data.get("garnishment_type") in garnishment_type_mapping:
                            order.garnishment_type_id = garnishment_type_mapping[order_data.get("garnishment_type")]
                        
                        orders_to_update.append(order)
                
                # Bulk update
                if orders_to_update:
                    GarnishmentOrder.objects.bulk_update(
                        orders_to_update,
                        ['is_consumer_debt', 'issued_date', 'received_date', 'start_date', 'stop_date',
                         'deduction_code', 'ordered_amount', 'fein', 'garnishing_authority', 'withholding_amount',
                         'garnishment_fees', 'fips_code', 'payee', 'override_amount', 'override_start_date',
                         'override_stop_date', 'paid_till_date', 'arrear_greater_than_12_weeks', 'arrear_amount',
                         'current_child_support', 'current_medical_support', 'current_spousal_support',
                         'medical_support_arrear', 'child_support_arrear', 'spousal_support_arrear',
                         'issuing_state_id', 'garnishment_type_id', 'updated_at']
                    )
                    
        except Exception as e:
            raise Exception(f"Bulk update failed: {str(e)}")
        

class GarnishmentOrderDetails(APIView):
    """
    API view for CRUD operations on garnishment order details.
    Provides robust exception handling and clear response messages.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', GarnishmentOrderSerializer(many=True)),
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, case_id=None):
        """
        Retrieve garnishment order details by case_id or all orders if case_id is not provided.
        """
        try:
            if case_id:
                try:
                    order = GarnishmentOrder.objects.get(case_id=case_id)
                    serializer = GarnishmentOrderSerializer(order)
                    return ResponseHelper.success_response(
                        f'Garnishment order details for case_id "{case_id}" fetched successfully',
                        serializer.data
                    )
                except GarnishmentOrder.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'case_id "{case_id}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                orders = GarnishmentOrder.objects.all()
                serializer = GarnishmentOrderSerializer(orders, many=True)
                return ResponseHelper.success_response(
                    'All data fetched successfully',
                    serializer.data
                )
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentOrderSerializer,
        responses={
            201: openapi.Response('Created', GarnishmentOrderSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new garnishment order.
        """
        try:
            serializer = GarnishmentOrderSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Data created successfully',
                    serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while creating data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentOrderSerializer,
        responses={
            200: openapi.Response('Updated', GarnishmentOrderSerializer),
            400: 'Invalid data',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, case_id=None):
        """
        Update an existing garnishment order by case_id.
        """
        if not case_id:
            return ResponseHelper.error_response(
                'case_id is required in URL to update data',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            order = GarnishmentOrder.objects.get(case_id=case_id)
        except GarnishmentOrder.DoesNotExist:
            return ResponseHelper.error_response(
                f'case_id "{case_id}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        try:
            serializer = GarnishmentOrderSerializer(order, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Data updated successfully',
                    serializer.data
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while updating data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'Deleted successfully',
            400: 'case_id is required in URL to delete data',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, case_id=None):
        """
        Delete a garnishment order by case_id.
        """
        if not case_id:
            return ResponseHelper.error_response(
                'case_id is required in URL to delete data',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            order = GarnishmentOrder.objects.get(case_id=case_id)
            order.delete()
            return ResponseHelper.success_response(
                f'Data for case_id "{case_id}" deleted successfully'
            )
        except GarnishmentOrder.DoesNotExist:
            return ResponseHelper.error_response(
                f'case_id "{case_id}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while deleting data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpsertGarnishmentOrderView(APIView):
    """
    API view to upsert (insert or update) garnishment orders from an uploaded Excel or CSV file.
    Optimized for bulk processing with minimal database queries.
    """
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Excel file to upload"
            ),
            openapi.Parameter(
                name='title',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Optional title"
            )
        ],
        responses={
            200: 'File uploaded and processed successfully',
            400: 'No file uploaded or unsupported file format',
            500: 'Internal server error'
        },
    )
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                return Response({'error': 'Unsupported file format. Use CSV or Excel.'}, status=status.HTTP_400_BAD_REQUEST)

            # Normalize column names
            df.rename(columns=lambda c: DataProcessingUtils.normalize_field_name(c), inplace=True)

            # Process data in batches for better performance
            batch_size = 200
            added_orders = []
            updated_orders = []
            validation_errors = []
            
            # Pre-fetch existing orders to avoid repeated queries
            existing_case_ids = set(GarnishmentOrder.objects.values_list('case_id', flat=True))
            
            # Pre-fetch all foreign key mappings to avoid repeated queries
            from user_app.models import EmployeeDetail
            from processor.models import State, GarnishmentType
            
            employee_mapping = {emp.ee_id: emp.id for emp in EmployeeDetail.objects.all()}
            employee_ssn_mapping = {str(emp.ssn).strip(): emp.id for emp in EmployeeDetail.objects.exclude(ssn__isnull=True).exclude(ssn='')}
            # Create case-insensitive mappings for state and garnishment type
            state_mapping = {(s.state or '').lower(): s.id for s in State.objects.all()}
            garnishment_type_mapping = {(gt.type or '').lower(): gt.id for gt in GarnishmentType.objects.all()}
            
            # Process data in batches
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                
                batch_orders_to_create = []
                batch_orders_to_update = []
                
                for _, row in batch_df.iterrows():
                    try:
                        # Process row data efficiently
                        order_data = self._process_order_row(row)
                        
                        if not order_data:
                            validation_errors.append(f"Row {batch_start + _ + 1}: No order data after processing")
                            continue
                            
                        case_id = order_data.get("case_id")
                        if not case_id:
                            validation_errors.append(f"Row {batch_start + _ + 1}: Missing case_id")
                            continue

                        # Check if order exists
                        if case_id in existing_case_ids:
                            # Prepare for update
                            batch_orders_to_update.append((case_id, order_data))
                            updated_orders.append(case_id)
                        else:
                            # Prepare for creation
                            batch_orders_to_create.append(order_data)

                    except Exception as row_e:
                        validation_errors.append(f"Row {batch_start + _ + 1}: {str(row_e)}")
                        continue
                
                # Bulk create new orders
                if batch_orders_to_create:
                    created_case_ids, skip_reasons = self._bulk_create_orders(batch_orders_to_create, employee_mapping, employee_ssn_mapping, state_mapping, garnishment_type_mapping)
                    added_orders.extend(created_case_ids)
                    validation_errors.extend(skip_reasons[:20])  # Add first 20 detailed skip reasons
                    # Update existing_case_ids set to include newly created orders
                    existing_case_ids.update(created_case_ids)
                
                # Bulk update existing orders
                if batch_orders_to_update:
                    self._bulk_update_orders(batch_orders_to_update, employee_mapping, state_mapping, garnishment_type_mapping)
            
            # Build response data
            response_data = {
                "added_count": len(added_orders),
                "updated_count": len(updated_orders),
                "validation_errors_count": len(validation_errors)
            }
            
            if added_orders:
                response_data["added_orders"] = added_orders[:200]  # Limit response size to prevent huge responses
                if len(added_orders) > 200:
                    response_data["added_orders_truncated"] = True
            
            if updated_orders:
                response_data["updated_orders"] = updated_orders[:200]  # Limit response size to prevent huge responses
                if len(updated_orders) > 200:
                    response_data["updated_orders_truncated"] = True
            
            if validation_errors:
                response_data["validation_errors"] = validation_errors[:20]  # Limit error details
                if len(validation_errors) > 20:
                    response_data["validation_errors_truncated"] = True
            
            # If no records were added or updated
            if not added_orders and not updated_orders:
                # If there are validation errors, return 400 Bad Request
                if validation_errors:
                    return Response({
                        'success': False,
                        'status_code': status.HTTP_400_BAD_REQUEST,
                        'message': 'No valid data to process. All records failed validation.',
                        'error': response_data
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # No data and no errors - could be empty file or all duplicate
                    return Response({
                        'success': True,
                        'status_code': status.HTTP_200_OK,
                        'message': 'No data was updated or inserted.',
                        'data': response_data
                    }, status=status.HTTP_200_OK)

            # If some records succeeded but there were also validation errors
            if validation_errors:
                return Response({
                    'success': True,
                    'status_code': status.HTTP_200_OK,
                    'message': 'File processed with some errors',
                    'data': response_data
                }, status=status.HTTP_200_OK)

            # All records succeeded without errors
            return Response({
                'success': True,
                'status_code': status.HTTP_200_OK,
                'message': 'File processed successfully',
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_order_row(self, row):
        """Process a single order row efficiently."""
        try:
            # Normalize column names first
            normalized_row = {}
            for key, value in row.items():
                if key and not str(key).startswith('Unnamed'):
                    normalized_key = DataProcessingUtils.normalize_field_name(key)
                    normalized_row[normalized_key] = value
                else:
                    normalized_row[key] = value

            # Define date fields that need parsing
            date_fields = [
                "override_start_date", "override_stop_date", "paid_till_date",
                "issued_date", "received_date", "start_date", "stop_date"
            ]
            
            # Parse date fields using the utility function
            for field in date_fields:
                if field in normalized_row:
                    normalized_row[field] = DataProcessingUtils.parse_date_field(normalized_row[field])
            
            # Clean and normalize data
            normalized_row = DataProcessingUtils.clean_data_row(normalized_row)
            
            return normalized_row
            
        except Exception as e:
            raise Exception(f"Error processing row: {str(e)}")
    
    def _bulk_create_orders(self, orders_data, employee_mapping, employee_ssn_mapping, state_mapping, garnishment_type_mapping):
        """Bulk create orders using bulk_create for better performance. Returns list of successfully created case_ids."""
        if not orders_data:
            return []
            
        created_case_ids = []
        try:
            from django.db import transaction
            
            with transaction.atomic():
                # Prepare bulk insert data
                bulk_orders = []
                for order_data in orders_data:
                    try:
                        # Resolve foreign keys
                        ee_id = order_data.get("ee_id")
                        ssn = order_data.get("ssn")
                        issuing_state = order_data.get("issuing_state")
                        garnishment_type = order_data.get("garnishment_type")
                        case_id = order_data.get("case_id")
                        
                        # Find employee by ee_id or ssn
                        employee_id = None
                        if ee_id and ee_id in employee_mapping:
                            employee_id = employee_mapping[ee_id]
                        elif ssn:
                            # Try to find by SSN if ee_id not found
                            key = str(ssn).strip()
                            employee_id = employee_ssn_mapping.get(key)
                        
                        if not employee_id:
                            continue  # Skip if no valid employee found
                        
                        # Validate required foreign keys (case-insensitive)
                        issuing_state_id = state_mapping.get((issuing_state or '').lower())
                        garnishment_type_id = garnishment_type_mapping.get((garnishment_type or '').lower())
                        
                        if not issuing_state_id:
                            continue  # Skip if issuing_state is missing or invalid
                        if not garnishment_type_id:
                            continue  # Skip if garnishment_type is missing or invalid
                        
                        bulk_orders.append(GarnishmentOrder(
                            case_id=case_id,
                            employee_id=employee_id,
                            issuing_state_id=issuing_state_id,
                            garnishment_type_id=garnishment_type_id,
                            is_consumer_debt=order_data.get("is_consumer_debt", False),
                            issued_date=order_data.get("issued_date"),
                            received_date=order_data.get("received_date"),
                            start_date=order_data.get("start_date"),
                            stop_date=order_data.get("stop_date"),
                            deduction_code=order_data.get("deduction_code", ""),
                            ordered_amount=order_data.get("ordered_amount", 0.00),
                            fein=order_data.get("fein", ""),
                            garnishing_authority=order_data.get("garnishing_authority"),
                            withholding_amount=order_data.get("withholding_amount", 0.00),
                            garnishment_fees=order_data.get("garnishment_fees", 0.00),
                            fips_code=order_data.get("fips_code"),
                            payee=order_data.get("payee"),
                            override_amount=order_data.get("override_amount"),
                            override_start_date=order_data.get("override_start_date"),
                            override_stop_date=order_data.get("override_stop_date"),
                            paid_till_date=order_data.get("paid_till_date"),
                            arrear_greater_than_12_weeks=order_data.get("arrear_greater_than_12_weeks", False),
                            arrear_amount=order_data.get("arrear_amount"),
                            current_child_support=order_data.get("current_child_support"),
                            current_medical_support=order_data.get("current_medical_support"),
                            current_spousal_support=order_data.get("current_spousal_support"),
                            medical_support_arrear=order_data.get("medical_support_arrear"),
                            child_support_arrear=order_data.get("child_support_arrear"),
                            spousal_support_arrear=order_data.get("spousal_support_arrear"),
                        ))
                        created_case_ids.append(case_id)
                    except Exception as e:
                        continue  # Skip problematic records
                
                # Bulk create
                if bulk_orders:
                    GarnishmentOrder.objects.bulk_create(bulk_orders, ignore_conflicts=True)
                
                return created_case_ids
                    
        except Exception as e:
            raise Exception(f"Bulk create failed: {str(e)}")
    
    def _bulk_update_orders(self, orders_data, employee_mapping, state_mapping, garnishment_type_mapping):
        """Bulk update orders efficiently."""
        if not orders_data:
            return
            
        try:
            from django.db import transaction
            
            with transaction.atomic():
                # Get existing orders
                case_ids = [order[0] for order in orders_data]
                existing_orders = {
                    order.case_id: order for order in GarnishmentOrder.objects.filter(case_id__in=case_ids)
                }
                
                orders_to_update = []
                for case_id, order_data in orders_data:
                    if case_id in existing_orders:
                        order = existing_orders[case_id]
                        
                        # Update fields
                        order.is_consumer_debt = order_data.get("is_consumer_debt", order.is_consumer_debt)
                        order.issued_date = order_data.get("issued_date", order.issued_date)
                        order.received_date = order_data.get("received_date", order.received_date)
                        order.start_date = order_data.get("start_date", order.start_date)
                        order.stop_date = order_data.get("stop_date", order.stop_date)
                        order.deduction_code = order_data.get("deduction_code", order.deduction_code)
                        order.ordered_amount = order_data.get("ordered_amount", order.ordered_amount)
                        order.fein = order_data.get("fein", order.fein)
                        order.garnishing_authority = order_data.get("garnishing_authority", order.garnishing_authority)
                        order.withholding_amount = order_data.get("withholding_amount", order.withholding_amount)
                        order.garnishment_fees = order_data.get("garnishment_fees", order.garnishment_fees)
                        order.fips_code = order_data.get("fips_code", order.fips_code)
                        order.payee = order_data.get("payee", order.payee)
                        order.override_amount = order_data.get("override_amount", order.override_amount)
                        order.override_start_date = order_data.get("override_start_date", order.override_start_date)
                        order.override_stop_date = order_data.get("override_stop_date", order.override_stop_date)
                        order.paid_till_date = order_data.get("paid_till_date", order.paid_till_date)
                        order.arrear_greater_than_12_weeks = order_data.get("arrear_greater_than_12_weeks", order.arrear_greater_than_12_weeks)
                        order.arrear_amount = order_data.get("arrear_amount", order.arrear_amount)
                        order.current_child_support = order_data.get("current_child_support", order.current_child_support)
                        order.current_medical_support = order_data.get("current_medical_support", order.current_medical_support)
                        order.current_spousal_support = order_data.get("current_spousal_support", order.current_spousal_support)
                        order.medical_support_arrear = order_data.get("medical_support_arrear", order.medical_support_arrear)
                        order.child_support_arrear = order_data.get("child_support_arrear", order.child_support_arrear)
                        order.spousal_support_arrear = order_data.get("spousal_support_arrear", order.spousal_support_arrear)
                        
                        # Update foreign keys if provided
                        if order_data.get("issuing_state") and order_data.get("issuing_state") in state_mapping:
                            order.issuing_state_id = state_mapping[order_data.get("issuing_state")]
                        if order_data.get("garnishment_type") and order_data.get("garnishment_type") in garnishment_type_mapping:
                            order.garnishment_type_id = garnishment_type_mapping[order_data.get("garnishment_type")]
                        
                        orders_to_update.append(order)
                
                # Bulk update
                if orders_to_update:
                    GarnishmentOrder.objects.bulk_update(
                        orders_to_update,
                        ['is_consumer_debt', 'issued_date', 'received_date', 'start_date', 'stop_date',
                         'deduction_code', 'ordered_amount', 'fein', 'garnishing_authority', 'withholding_amount',
                         'garnishment_fees', 'fips_code', 'payee', 'override_amount', 'override_start_date',
                         'override_stop_date', 'paid_till_date', 'arrear_greater_than_12_weeks', 'arrear_amount',
                         'current_child_support', 'current_medical_support', 'current_spousal_support',
                         'medical_support_arrear', 'child_support_arrear', 'spousal_support_arrear',
                         'issuing_state_id', 'garnishment_type_id', 'updated_at']
                    )
                    
        except Exception as e:
            raise Exception(f"Bulk update failed: {str(e)}")


class ExportGarnishmentOrderDataView(APIView):
    """
    API view to export garnishment order data as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    @swagger_auto_schema(
        responses={
            200: 'Excel file exported successfully',
            404: 'No garnishment orders found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Handles GET request to export all garnishment orders to an Excel file.
        """
        try:
            # Fetch all garnishment orders from the database
            orders = GarnishmentOrder.objects.all()
            if not orders.exists():
                return ResponseHelper.error_response(
                    message="No garnishment orders found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = GarnishmentOrderSerializer(orders, many=True)

            # Create Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Garnishment Orders"

            # Define header fields (use constants where available)
            header_fields = [
            "id",EE.CASE_ID,EE.SSN,EE.EMPLOYEE_ID,"issuing_state","garnishment_type","garnishment_fees","payee","override_amount","override_start_date","override_stop_date","paid_till_date","is_consumer_debt","issued_date","received_date","start_date","stop_date","ordered_amount","garnishing_authority","withholding_amount","current_child_support","current_medical_support","child_support_arrear","medical_support_arrear","current_spousal_support","spousal_support_arrear","fips_code","arrear_greater_than_12_weeks",CA.ARREAR_AMOUNT,"created_at","updated_at"]

            ws.append(header_fields)

            # Write data rows to the worksheet
            for order in serializer.data:
                row = [order.get(field, '') for field in header_fields]
                ws.append(row)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'garnishment_orders_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            # logger.error(f"Error exporting garnishment order data: {e}")
            return ResponseHelper.error_response(
                message="Failed to export garnishment order data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GarnishmentOrderAPI(APIView):
    """
    List and Create Garnishment Orders.
    Uses meaningful fields (not raw IDs) in input/output.
    """

    @swagger_auto_schema(
        responses={200: GarnishmentOrderSerializer(many=True)}
    )
    def get(self, request):
        try:
            # Optimized queryset to avoid N+1 and reduce columns
            queryset = (
                GarnishmentOrder.objects
                .select_related('employee', 'issuing_state', 'garnishment_type')
                .only(
                    'id', 'case_id',
                    'employee__ssn',
                    'issuing_state__state',
                    'garnishment_type__type',
                    'garnishment_fees', 'payee', 'override_amount',
                    'override_start_date', 'override_stop_date', 'paid_till_date',
                    'is_consumer_debt', 'issued_date', 'received_date', 'start_date', 'stop_date',
                    'ordered_amount', 'garnishing_authority', 'withholding_amount',
                    'current_child_support', 'current_medical_support',
                    'child_support_arrear', 'medical_support_arrear',
                    'current_spousal_support', 'spousal_support_arrear',
                    'fips_code', 'arrear_greater_than_12_weeks', 'arrear_amount',
                    'created_at', 'updated_at'
                )
                .order_by('-created_at')
            )

            # Chunked pagination (defaults if not provided)
            page = request.query_params.get('page') or 1
            page_size = request.query_params.get('page_size') or 500
            try:
                page = int(page)
                page_size = max(1, min(1000, int(page_size)))
                from django.core.paginator import Paginator, EmptyPage
                paginator = Paginator(queryset, page_size)
                page_obj = paginator.page(page)
                serializer = GarnishmentOrderSerializer(page_obj.object_list, many=True)
                return ResponseHelper.success_response(
                    message="Garnishment orders fetched successfully",
                    data={
                        'results': serializer.data,
                        'page': page,
                        'page_size': page_size,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                    },
                    status_code=status.HTTP_200_OK
                )
            except (ValueError, EmptyPage):
                return ResponseHelper.error_response(
                    message="Invalid page or page_size",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to fetch garnishment orders",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentOrderSerializer,
        responses={201: GarnishmentOrderSerializer, 400: "Validation Error"}
    )
    def post(self, request):
        serializer = GarnishmentOrderSerializer(data=request.data)
        if serializer.is_valid():
            try:
                order = serializer.save()
                return ResponseHelper.success_response(
                    message="Garnishment order created successfully",
                    data=GarnishmentOrderSerializer(order).data,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to create garnishment order",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while creating garnishment order",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class GarnishmentOrderDetailAPI(APIView):
    """
    Retrieve, Update, or Delete a specific Garnishment Order.
    """

    def get_object(self, pk):
        try:
            return GarnishmentOrder.objects.get(pk=pk)
        except GarnishmentOrder.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={200: GarnishmentOrderSerializer, 404: "Not Found"}
    )
    def get(self, request, pk):
        order = self.get_object(pk)
        if not order:
            return ResponseHelper.error_response(
                message="Garnishment order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        return ResponseHelper.success_response(
            message="Garnishment order fetched successfully",
            data=GarnishmentOrderSerializer(order).data,
            status_code=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        request_body=GarnishmentOrderSerializer,
        responses={200: GarnishmentOrderSerializer, 400: "Validation Error", 404: "Not Found"}
    )
    def put(self, request, pk):
        order = self.get_object(pk)
        if not order:
            return ResponseHelper.error_response(
                message="Garnishment order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = GarnishmentOrderSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                order = serializer.save()
                return ResponseHelper.success_response(
                    message="Garnishment order updated successfully",
                    data=GarnishmentOrderSerializer(order).data,
                    status_code=status.HTTP_200_OK
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to update garnishment order",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while updating garnishment order",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    @swagger_auto_schema(
        responses={204: "Deleted", 404: "Not Found"}
    )
    def delete(self, request, pk):
        order = self.get_object(pk)
        if not order:
            return ResponseHelper.error_response(
                message="Garnishment order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            order.delete()
            return ResponseHelper.success_response(
                message="Garnishment order deleted successfully",
                data={},
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to delete garnishment order",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
