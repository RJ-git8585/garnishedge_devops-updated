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

class GarnishmentOrderImportView(APIView):
    """
    API view to handle the import of garnishment orders from a file.
    Provides robust exception handling and clear response messages.
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
            
            added_orders = []
            updated_orders = []
            
            for _, row in df.iterrows():
                try:
                    # Define date fields that need parsing
                    date_fields = [
                        "override_start_date", "override_stop_date", "paid_till_date",
                        "issued_date", "received_date", "start_date", "stop_date"
                    ]
                    
                    order_data = {
                        EE.CASE_ID: row.get(EE.CASE_ID),
                        "ssn": row.get("ssn"),
                        "issuing_state": row.get("issuing_state"),
                        "garnishment_type": row.get("garnishment_type"),
                        "garnishment_fees": row.get("garnishment_fees"),
                        "payee": row.get("payee"),
                        "override_amount": row.get("override_amount"),
                        "is_consumer_debt": row.get("is_consumer_debt"),
                        "ordered_amount": row.get("ordered_amount"),
                        "garnishing_authority": row.get("garnishing_authority"),
                        "withholding_amount": row.get("withholding_amount"),
                        "current_child_support": row.get("current_child_support"),
                        "current_medical_support": row.get("current_medical_support"),
                        "child_support_arrear": row.get("child_support_arrear"),
                        "medical_support_arrear": row.get("medical_support_arrear"),
                        "current_spousal_support": row.get("current_spousal_support"),
                        "spousal_support_arrear": row.get("spousal_support_arrear"),
                        "fips_code": row.get("fips_code"),
                        "arrear_greater_than_12_weeks": row.get("arrear_greater_than_12_weeks"),
                        "arrear_amount": row.get("arrear_amount"),
                    }
                    
                    # Parse date fields using the utility function
                    for date_field in date_fields:
                        order_data[date_field] = DataProcessingUtils.parse_date_field(row.get(date_field))
                    
                    # Check if case_id exists
                    case_id = order_data.get("case_id")
                    if not case_id:
                        # Skip rows without case_id
                        continue
                    
                    # Try to find existing order by case_id
                    existing_order = GarnishmentOrder.objects.filter(case_id=case_id).first()
                    
                    if existing_order:
                        # Update existing order
                        serializer = GarnishmentOrderSerializer(
                            existing_order, 
                            data=order_data, 
                            partial=True
                        )
                        if serializer.is_valid():
                            serializer.save()
                            updated_orders.append(case_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for case_id {case_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new order
                        serializer = GarnishmentOrderSerializer(data=order_data)
                        if serializer.is_valid():
                            serializer.save()
                            added_orders.append(case_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for case_id {case_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                            
                except Exception as row_e:
                    return ResponseHelper.error_response(
                        message="Error processing row",
                        error=str(row_e),
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Build response data
            response_data = {}
            
            if added_orders:
                response_data["added_orders"] = added_orders
                response_data["added_count"] = len(added_orders)
            
            if updated_orders:
                response_data["updated_orders"] = updated_orders
                response_data["updated_count"] = len(updated_orders)
            
            if not added_orders and not updated_orders:
                return ResponseHelper.success_response(
                    message="No valid data to process",
                    data=response_data,
                    status_code=status.HTTP_200_OK
                )

            return ResponseHelper.success_response(
                message="File processed successfully",
                data=response_data,
                status_code=status.HTTP_201_CREATED
            )

        except Exception as e:
            # logger.error(f"Error importing garnishment orders: {e}")
            return ResponseHelper.error_response(
                message="Failed to import garnishment orders",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

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
    Provides robust exception handling and clear response messages.
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
                data = list(csv.DictReader(
                    file.read().decode('utf-8').splitlines()))
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
                data = df.to_dict(orient='records')
            else:
                return Response({'error': 'Unsupported file format. Use CSV or Excel.'}, status=status.HTTP_400_BAD_REQUEST)

            added_orders, updated_orders = [], []

            for row in data:
                # Clean up row keys and values
                row = {k: v for k, v in row.items() if k and not str(
                    k).startswith('Unnamed')}

                # Define date fields that need parsing
                date_fields = [
                    "override_start_date", "override_stop_date", "paid_till_date",
                    "issued_date", "received_date", "start_date", "stop_date"
                ]
                
                # Parse date fields using the utility function
                for field in date_fields:
                    if field in row:
                        row[field] = DataProcessingUtils.parse_date_field(row[field])

                case_id = row.get(EE.CASE_ID)
                if not case_id:
                    # Skip row if unique identifiers are missing
                    continue

                obj = GarnishmentOrder.objects.filter(case_id=case_id).first()

                if obj:
                    # Only update if there are changes
                    has_changes = any(
                        str(getattr(obj, field, '')).strip() != str(
                            row.get(field, '')).strip()
                        for field in row.keys()
                        if hasattr(obj, field)
                    )
                    if has_changes:
                        serializer = GarnishmentOrderSerializer(
                            obj, data=row, partial=True)
                        if serializer.is_valid():
                            serializer.save()
                            updated_orders.append(case_id)
                else:
                    serializer = GarnishmentOrderSerializer(data=row)
                    if serializer.is_valid():
                        serializer.save()
                        added_orders.append(case_id)

            response_data = []
            if added_orders:
                response_data.append({
                    'message': 'Garnishment order(s) added successfully',
                    'added_orders': added_orders
                })
            if updated_orders:
                response_data.append({
                    'message': 'Garnishment order(s) updated successfully',
                    'updated_orders': updated_orders
                })

            if not response_data:
                return Response({
                    'success': True,
                    'status_code': status.HTTP_200_OK,
                    'message': 'No data was updated or inserted.'
                }, status=status.HTTP_200_OK)

            return Response({
                'success': True,
                'status_code': status.HTTP_200_OK,
                'response_data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            # logger.error(f"Error upserting garnishment orders: {e}")
            return Response({
                'success': False,
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            orders = GarnishmentOrder.objects.all().order_by("-created_at")
            # result = PaginationHelper.paginate_queryset(
            #     orders, request, GarnishmentOrderSerializer
            # )
            serializer = GarnishmentOrderSerializer(orders, many=True)
            return ResponseHelper.success_response(
                message="Garnishment orders fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
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
