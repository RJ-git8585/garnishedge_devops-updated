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
from garnishedge_project.audit_decorators import (
    audit_api_call, 
    audit_business_operation, 
    audit_data_access,
    audit_security_event
)
from rest_framework.response import Response
from rest_framework.views import APIView
from user_app.models import EmployeeDetail, GarnishmentOrder
from processor.models import GarnishmentFees
from user_app.serializers import EmployeeDetailsSerializer
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
        responses={
            200: "File uploaded successfully",
            400: "Row import error",
            500: "Internal server error"
        },
    )
    @audit_api_call
    @audit_business_operation("employee_bulk_import")
    @audit_data_access("EmployeeDetail", "CREATE")
    @audit_security_event("bulk_data_import", "CRITICAL")
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

            for _, row in df.iterrows():
                try:
                    # Convert each row to dict directly — no validation or defaults
                    employee_data = dict(row)

                    # Directly serialize and save
                    serializer = EmployeeDetailsSerializer(data=employee_data)
                    if serializer.is_valid():
                        employees.append(serializer.save())
                    else:
                        print(f"Serializer validation failed for row: {serializer.errors}")
                        continue

                except Exception as row_exc:
                    print(f"Error processing row: {str(row_exc)}")
                    continue

            response_data = {
                "imported_count": len(employees),
                "total_rows_processed": len(df),
                "successful_imports": len(employees),
                "failed_imports": len(df) - len(employees)
            }

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



class EmployeeDetailsAPIViews(APIView):
    """
    API view for CRUD operations on employee details.
    Provides robust exception handling and clear response messages.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', EmployeeDetailsSerializer(many=True)),
            404: 'Employee not found',
            500: 'Internal server error'
        }
    )
    @audit_api_call
    def get(self, request, case_id=None, ee_id=None):
        """
        Retrieve employee details by case_id and ee_id, or all employees if not provided.
        """
        try:
            if case_id and ee_id:
                try:
                    employee = EmployeeDetail.objects.get(
                        case_id=case_id, ee_id=ee_id)
                    serializer = EmployeeDetailsSerializer(employee)
                    return ResponseHelper.success_response('Employee data fetched successfully', serializer.data)
                except EmployeeDetail.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'Employee with case_id "{case_id}" and ee_id "{ee_id}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                employees = EmployeeDetail.objects.all()
                serializer = EmployeeDetailsSerializer(employees, many=True)

                return ResponseHelper.success_response('All data fetched successfully', serializer.data)
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=EmployeeDetailsSerializer,
        responses={
            201: openapi.Response('Created', EmployeeDetailsSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new employee detail record.
        """
        try:
            serializer = EmployeeDetailsSerializer(data=request.data)
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
        request_body=EmployeeDetailsSerializer,
        responses={
            200: openapi.Response('Updated', EmployeeDetailsSerializer),
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
            serializer = EmployeeDetailsSerializer(employee, data=request.data)
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
    API view to handle the import/upsert of employee details from a file.
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
            
            added_employees = []
            updated_employees = []
            
            for _, row in df.iterrows():
                try:
                    # Define date fields that need parsing
                    date_fields = [
                        "garnishment_fees_suspended_till"
                    ]
                    
                    employee_data = {
                        EE.EMPLOYEE_ID: row.get(EE.EMPLOYEE_ID),
                        EE.CLIENT_ID: row.get(EE.CLIENT_ID),
                        EE.FIRST_NAME: row.get(EE.FIRST_NAME),
                        EE.MIDDLE_NAME: row.get(EE.MIDDLE_NAME),
                        EE.LAST_NAME: row.get(EE.LAST_NAME),
                        EE.SSN: row.get(EE.SSN),
                        EE.HOME_STATE: row.get(EE.HOME_STATE),
                        EE.WORK_STATE: row.get(EE.WORK_STATE),
                        EE.GENDER: row.get(EE.GENDER),
                        "number_of_exemptions": row.get("number_of_exemptions"),
                        EE.FILING_STATUS: row.get(EE.FILING_STATUS),
                        EE.MARITAL_STATUS: row.get(EE.MARITAL_STATUS),
                        "number_of_student_default_loan": row.get("number_of_student_default_loan"),
                        "number_of_dependent_child": row.get("number_of_dependent_child"),
                        EE.SUPPORT_SECOND_FAMILY: row.get(EE.SUPPORT_SECOND_FAMILY),
                        EE.GARNISHMENT_FEES_STATUS: row.get(EE.GARNISHMENT_FEES_STATUS),
                        EE.NUMBER_OF_ACTIVE_GARNISHMENT: row.get(EE.NUMBER_OF_ACTIVE_GARNISHMENT),
                        CF.IS_ACTIVE: row.get(CF.IS_ACTIVE, True),
                    }
                    
                    # Parse date fields using the utility function
                    for date_field in date_fields:
                        employee_data[date_field] = DataProcessingUtils.parse_date_field(row.get(date_field))
                    
                    # Clean and normalize row data using utility functions
                    employee_data = DataProcessingUtils.clean_data_row(employee_data)
                    
                    # Apply basic data cleaning without strict validation
                    employee_data = DataProcessingUtils.validate_and_clean_employee_data(employee_data)
                    
                    # Check if ee_id exists
                    ee_id = employee_data.get(EE.EMPLOYEE_ID)
                    if not ee_id:
                        # Skip rows without ee_id
                        continue
                    
                    # Try to create missing client if needed
                    client_id = employee_data.get(EE.CLIENT_ID)
                    if client_id and not DataProcessingUtils.validate_client_exists(client_id):
                        DataProcessingUtils.create_missing_client(client_id)
                    
                    # Provide default values for required fields if missing
                    if not employee_data.get(EE.FILING_STATUS):
                        employee_data[EE.FILING_STATUS] = DataProcessingUtils.get_default_filing_status()
                    
                    if not employee_data.get(EE.MARITAL_STATUS):
                        employee_data[EE.MARITAL_STATUS] = DataProcessingUtils.get_default_marital_status()
                    
                    # Try to find existing employee by ee_id
                    existing_employee = EmployeeDetail.objects.filter(ee_id=ee_id).first()
                    
                    if existing_employee:
                        # Update existing employee
                        serializer = EmployeeDetailsSerializer(
                            existing_employee, 
                            data=employee_data, 
                            partial=True
                        )
                        if serializer.is_valid():
                            serializer.save()
                            updated_employees.append(ee_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for ee_id {ee_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new employee
                        serializer = EmployeeDetailsSerializer(data=employee_data)
                        if serializer.is_valid():
                            serializer.save()
                            added_employees.append(ee_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for ee_id {ee_id}",
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
            
            if added_employees:
                response_data["added_employees"] = added_employees
                response_data["added_count"] = len(added_employees)
            
            if updated_employees:
                response_data["updated_employees"] = updated_employees
                response_data["updated_count"] = len(updated_employees)
            
            if not added_employees and not updated_employees:
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
            return ResponseHelper.error_response(
                message="Failed to import employee data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Export employee details using the Excel file
class ExportEmployeeDataView(APIView):
    """
    Exports employee details as an Excel file.
    Provides robust exception handling and clear response messages.
    """
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

            serializer = EmployeeDetailsSerializer(employees, many=True)

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


class EmployeeDetailsAPI(APIView):
    """
    API view for listing and creating Employee Details.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", EmployeeDetailsSerializer(many=True)),
            500: "Internal Server Error",
        }
    )
    # @audit_api_call
    # @audit_business_operation("employee_list_retrieval")
    # @audit_data_access("EmployeeDetail", "READ")
    def get(self, request):
        """
        Get paginated list of active employees.
        """
        try:
            employees = EmployeeDetail.objects.all().order_by("-created_at")
            result = EmployeeDetailsSerializer(employees, many=True)
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
        request_body=EmployeeDetailsSerializer,
        responses={
            201: openapi.Response("Created", EmployeeDetailsSerializer),
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    @audit_api_call
    @audit_business_operation("employee_creation")
    @audit_data_access("EmployeeDetail", "CREATE")
    @audit_security_event("employee_data_modification", "WARNING")
    def post(self, request):
        """
        Create a new employee.
        """
        serializer = EmployeeDetailsSerializer(data=request.data)
        if serializer.is_valid():
            try:
                employee = serializer.save()
                
                # Log successful employee creation
                from garnishedge_project.audit_logger import audit_logger
                audit_logger.log_business_operation(
                    "employee_created",
                    {
                        "employee_id": employee.id,
                        "employee_name": getattr(employee, 'first_name', 'Unknown'),
                        "data_source": "api"
                    },
                    user=request.user,
                    success=True
                )
                
                return ResponseHelper.success_response(
                    message="Employee created successfully",
                    data=EmployeeDetailsSerializer(employee).data,
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


class EmployeeDetailsByIdAPI(APIView):
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
            200: openapi.Response("Success", EmployeeDetailsSerializer),
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
            data=EmployeeDetailsSerializer(employee).data,
            status_code=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        request_body=EmployeeDetailsSerializer,
        responses={
            200: openapi.Response("Updated", EmployeeDetailsSerializer),
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

        serializer = EmployeeDetailsSerializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                employee = serializer.save()
                return ResponseHelper.success_response(
                    message="Employee updated successfully",
                    data=EmployeeDetailsSerializer(employee).data,
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
