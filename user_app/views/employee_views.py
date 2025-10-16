from rest_framework import status
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from processor.garnishment_library.utils.response import ResponseHelper
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from io import BytesIO
import pandas as pd
from processor.garnishment_library import PaginationHelper
import math
from rest_framework.permissions import AllowAny
import csv
import re
from rest_framework.response import Response
from rest_framework.views import APIView
from user_app.models import EmployeeDetail, GarnishmentOrder
from processor.models import GarnishmentFees
from user_app.serializers import EmployeeDetailSerializer
from datetime import datetime
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    CommonFields as CF

)
from django.db.models import Prefetch, F
from user_app.utils import DataProcessingUtils


class EmployeeImportView(APIView):
    """
    Handles the import of employee details from an Excel or CSV file.
    """
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Excel or CSV file to upload"
            ),
            openapi.Parameter(
                name='title',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Optional title"
            )
        ],
        responses={200: "File uploaded successfully",
                   400: "Row import error",
                   500: "Internal server error"},
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

            employees = []


            validation_warnings = []
            for _, row in df.iterrows():
                try:
                    # Convert row to dict and clean data using utility functions
                    employee_data = dict(row)
                    employee_data = DataProcessingUtils.clean_data_row(employee_data)
                    
                    # Use the new validation and fixing function with auto client creation
                    cleaned_data, validation_errors = DataProcessingUtils.validate_and_fix_employee_data(employee_data, auto_create_client=True)
                    
                    # Collect validation warnings
                    validation_warnings.extend(validation_errors)
                    
                    # Check if there are critical errors (missing required fields)
                    critical_errors = [err for err in validation_errors if "not found" in err or "is required" in err]
                    if critical_errors:
                        error_data = {
                            "row_data": cleaned_data,
                            "errors": critical_errors,
                            "warnings": [err for err in validation_errors if err not in critical_errors]
                        }
                        # Make error data JSON-safe
                        error_data = DataProcessingUtils.make_json_safe(error_data)
                        return ResponseHelper.error_response(
                            message="Critical validation errors",
                            error=error_data,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    serializer = EmployeeDetailSerializer(data=cleaned_data)
                    if serializer.is_valid():
                        employees.append(serializer.save())
                    else:
                        error_data = {
                            "row_data": cleaned_data,
                            "serializer_errors": serializer.errors,
                            "validation_warnings": validation_errors
                        }
                        # Make error data JSON-safe
                        error_data = DataProcessingUtils.make_json_safe(error_data)
                        return ResponseHelper.error_response(
                            message="Serializer validation error",
                            error=error_data,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                except Exception as row_exc:
                    return ResponseHelper.error_response(
                        message="Row import error",
                        error=str(row_exc),
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            response_data = {
                "imported_count": len(employees),
                "total_rows_processed": len(df),
                "validation_warnings": validation_warnings if validation_warnings else None
            }
            
            # Make response data JSON-safe
            response_data = DataProcessingUtils.make_json_safe(response_data)
            
            return ResponseHelper.success_response(
                message="File processed successfully",
                data=response_data,
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to import employees",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmployeeDetailAPIViews(APIView):
    """
    API view for CRUD operations on employee details.
    Provides robust exception handling and clear response messages.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', EmployeeDetailSerializer(many=True)),
            404: 'Employee not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, case_id=None, ee_id=None):
        """
        Retrieve employee details by case_id and ee_id, or all employees if not provided.
        """
        try:
            if case_id and ee_id:
                try:
                    employee = EmployeeDetail.objects.get(
                        case_id=case_id, ee_id=ee_id)
                    serializer = EmployeeDetailSerializer(employee)
                    return ResponseHelper.success_response('Employee data fetched successfully', serializer.data)
                except EmployeeDetail.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'Employee with case_id "{case_id}" and ee_id "{ee_id}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                employees = EmployeeDetail.objects.all()
                serializer = EmployeeDetailSerializer(employees, many=True)

                return ResponseHelper.success_response('All data fetched successfully', serializer.data)
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=EmployeeDetailSerializer,
        responses={
            201: openapi.Response('Created', EmployeeDetailSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new employee detail record.
        """
        try:
            serializer = EmployeeDetailSerializer(data=request.data)
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
        request_body=EmployeeDetailSerializer,
        responses={
            200: openapi.Response('Updated', EmployeeDetailSerializer),
            400: 'Invalid data or missing identifiers',
            404: 'Employee not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, case_id=None, ee_id=None):
        """
        Update an existing employee detail record by case_id and ee_id.
        """
        if not case_id or not ee_id:
            return ResponseHelper.error_response(
                'Case ID and Employee ID are required in URL to update data',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            employee = EmployeeDetail.objects.get(
                case_id=case_id, ee_id=ee_id)
        except EmployeeDetail.DoesNotExist:
            return ResponseHelper.error_response(
                f'Employee with case_id "{case_id}" and ee_id "{ee_id}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        try:
            serializer = EmployeeDetailSerializer(employee, data=request.data)
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
            200: 'Employee deleted successfully',
            400: 'Case ID and Employee ID are required in URL to delete data',
            404: 'Employee not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, case_id=None, ee_id=None):
        """
        Delete an employee detail record by case_id and ee_id.
        """
        if not case_id or not ee_id:
            return ResponseHelper.error_response(
                'Case ID and Employee ID are required in URL to delete data',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            employee = EmployeeDetail.objects.get(
                case_id=case_id, ee_id=ee_id)
            employee.delete()
            return ResponseHelper.success_response(
                f'Employee with case_id "{case_id}" and ee_id "{ee_id}" deleted successfully'
            )
        except EmployeeDetail.DoesNotExist:
            return ResponseHelper.error_response(
                f'Employee with case_id "{case_id}" and ee_id "{ee_id}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while deleting data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpsertEmployeeDataView(APIView):
    """
    API endpoint to upsert (insert or update) employee details from an uploaded Excel or CSV file.
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
                description="Excel or CSV file to upload"
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
        """
        Upsert employee details from uploaded file.
        """
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read file data based on extension
            if file.name.endswith('.csv'):
                data = list(csv.DictReader(
                    file.read().decode('utf-8').splitlines()))
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
                data = df.to_dict(orient='records')
            else:
                return Response({'error': 'Unsupported file format. Use CSV or Excel.'}, status=status.HTTP_400_BAD_REQUEST)

            added_employees, updated_employees = [], []

            for row in data:
                # Clean and normalize row data using utility functions
                row = DataProcessingUtils.clean_data_row(row)
                
                # Use the new validation and fixing function with auto client creation
                cleaned_row, validation_errors = DataProcessingUtils.validate_and_fix_employee_data(row, auto_create_client=True)

                case_id = cleaned_row.get("case_id")
                ee_id = cleaned_row.get("ee_id")
                if not ee_id or not case_id:
                    continue  # Skip if identifiers are missing

                # Check if employee exists
                obj_qs = EmployeeDetail.objects.filter(
                    case_id=case_id, ee_id=ee_id)
                obj = obj_qs.first() if obj_qs.exists() else None

                if obj:
                    # Update only if there are changes
                    has_changes = any(
                        str(getattr(obj, field, '')).strip() != str(
                            cleaned_row.get(field, '')).strip()
                        for field in cleaned_row.keys()
                        if hasattr(obj, field)
                    )
                    if has_changes:
                        serializer = EmployeeDetailSerializer(
                            obj, data=cleaned_row, partial=True)
                        if serializer.is_valid():
                            serializer.save()
                            updated_employees.append(ee_id)
                else:
                    serializer = EmployeeDetailSerializer(data=cleaned_row)
                    if serializer.is_valid():
                        serializer.save()
                        added_employees.append(ee_id)

            response_data = []
            if added_employees:
                response_data.append({
                    'message': 'Employee(s) imported successfully',
                    'added_employees': added_employees
                })
            if updated_employees:
                response_data.append({
                    'message': 'Employee details updated successfully',
                    'updated_employees': updated_employees
                })

            if not response_data:
                return Response({
                    'success': True,
                    'status_code': status.HTTP_200_OK,
                    'message': 'No data was updated or inserted.'
                }, status=status.HTTP_200_OK)

            # Make response data JSON-safe
            response_data = DataProcessingUtils.make_json_safe(response_data)
            
            return Response({
                'success': True,
                'status_code': status.HTTP_200_OK,
                'response_data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            # logger.error(f"Error upserting employee data: {e}")
            return Response({
                'success': False,
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Export employee details using the Excel file
class ExportEmployeeDataView(APIView):
    """
    Exports employee details as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        responses={
            200: 'Employee data exported successfully as Excel file',
            404: 'No employees found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        try:
            employees = EmployeeDetail.objects.all()
            if not employees.exists():
                return ResponseHelper.error_response(
                    message="No employees found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = EmployeeDetailSerializer(employees, many=True)

            # Define Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Employee Data"


            # Define headers using constants where available
            header_fields = [
                EE.EMPLOYEE_ID, EE.SSN,EE.CLIENT_ID, EE.FIRST_NAME, EE.MIDDLE_NAME, EE.LAST_NAME, EE.GENDER, EE.HOME_STATE, EE.WORK_STATE,
                EE.MARITAL_STATUS, EE.FILING_STATUS,'number_of_exemptions',
                EE.SUPPORT_SECOND_FAMILY,'number_of_dependent_child',  
                'number_of_student_default_loan', EE.GARNISHMENT_FEES_STATUS, EE.GARNISHMENT_FEES_SUSPENDED_TILL, EE.NUMBER_OF_ACTIVE_GARNISHMENT, CF.IS_ACTIVE, CF.CREATED_AT, CF.UPDATED_AT
            ]
            ws.append(header_fields)

            # Append employee data
            for employee in serializer.data:
                row = [employee.get(field, '') for field in header_fields]
                ws.append(row)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'employee_details_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to export employee data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmployeeGarnishmentOrderCombineData(APIView):
    """
    API endpoint to combine employee, garnishment order, and garnishment fee data.
    Returns merged data or appropriate error messages.
    """

    @swagger_auto_schema(
        responses={
            200: 'Combined data fetched successfully',
            204: 'No matching data found',
            400: 'Missing required columns',
            500: 'Internal server error'
        }
    )

    def get(self, request):
        try:
            employees = EmployeeDetail.objects.prefetch_related(
                Prefetch(
                    'garnishment_orders',
                    queryset=GarnishmentOrder.objects.all()
                )
            )

            results = []
            for emp in employees:
                for garn in emp.garnishment_orders.all():
                    # Match GarnishmentFees based on state, type, and pay_period
                    fee = GarnishmentFees.objects.filter(
                        state__name__iexact=emp.work_state.strip(),
                        garnishment_type__name__iexact=garn.garnishment_type.strip(),
                        pay_period__name__iexact=emp.pay_period.strip()
                    ).first()

                    results.append({
                        "employee_id": emp.ee_id,
                        "case_id": emp.case_id,
                        "work_state": emp.work_state,
                        "garnishment_type": garn.garnishment_type,
                        "pay_period": emp.pay_period,
                        "fee_rule": fee.rule.rule if fee else None
                    })

            if not results:
                return Response(
                    {"message": "No matching data found"},
                    status=status.HTTP_204_NO_CONTENT
                )

            return Response({
                "success": True,
                "message": "Data fetched successfully",
                "status_code": status.HTTP_200_OK,
                "data": results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeDetailAPI(APIView):
    """
    API view for listing and creating Employee Details.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", EmployeeDetailSerializer(many=True)),
            500: "Internal Server Error",
        }
    )
    def get(self, request):
        """
        Get paginated list of active employees.
        """
        try:
            employees = EmployeeDetail.objects.all().order_by("-created_at")
            result = EmployeeDetailSerializer(employees, many=True)
            return ResponseHelper.success_response(
                message="Employees fetched successfully",
                data=result.data,
                status_code=status.HTTP_200_OK
            )  
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to fetch employees",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=EmployeeDetailSerializer,
        responses={
            201: openapi.Response("Created", EmployeeDetailSerializer),
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        """
        Create a new employee.
        """
        serializer = EmployeeDetailSerializer(data=request.data)
        if serializer.is_valid():
            try:
                employee = serializer.save()
                return ResponseHelper.success_response(
                    message="Employee created successfully",
                    data=EmployeeDetailSerializer(employee).data,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to create employee",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while creating employee",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class EmployeeDetailByIdAPI(APIView):
    """
    API view for retrieving, updating, or deleting a specific Employee by ID.
    """

    def get_object(self, pk):
        try:
            return EmployeeDetail.objects.get(pk=pk)
        except EmployeeDetail.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", EmployeeDetailSerializer),
            404: "Not Found",
        }
    )
    def get(self, request, pk):
        """
        Retrieve details of a specific employee.
        """
        employee = self.get_object(pk)
        if not employee:
            return ResponseHelper.error_response(
                message="Employee not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        return ResponseHelper.success_response(
            message="Employee fetched successfully",
            data=EmployeeDetailSerializer(employee).data,
            status_code=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        request_body=EmployeeDetailSerializer,
        responses={
            200: openapi.Response("Updated", EmployeeDetailSerializer),
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, pk):
        """
        Update an existing employee (partial updates supported).
        """
        employee = self.get_object(pk)
        if not employee:
            return ResponseHelper.error_response(
                message="Employee not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeDetailSerializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                employee = serializer.save()
                return ResponseHelper.success_response(
                    message="Employee updated successfully",
                    data=EmployeeDetailSerializer(employee).data,
                    status_code=status.HTTP_200_OK
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to update employee",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while updating employee",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    @swagger_auto_schema(
        responses={
            204: "Deleted",
            404: "Not Found",
            500: "Internal Server Error",
        }
    )
    def delete(self, request, pk):
        """
        Soft delete an employee (mark as inactive).
        """
        employee = self.get_object(pk)
        if not employee:
            return ResponseHelper.error_response(
                message="Employee not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            employee.is_active = False
            employee.save(update_fields=["is_active"])
            return ResponseHelper.success_response(
                message="Employee deleted successfully",
                data={},
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to delete employee",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
