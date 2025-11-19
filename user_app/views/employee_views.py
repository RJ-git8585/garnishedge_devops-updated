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
from user_app.models import EmployeeDetail, GarnishmentOrder, EmplopyeeAddress
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
from django.core.paginator import Paginator, EmptyPage


class EmployeeImportView(APIView):
    """
    Handles the import of employee details from an Excel or CSV file.
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

            pd.set_option('display.max_columns', None)

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
            # Explicit early check: if DataFrame is empty, return a clearer error
            if df.empty:
                return ResponseHelper.error_response(
                    message="No data rows found in the uploaded file",
                    error={
                        "rows": 0,
                        "columns": list(df.columns),
                    },
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Normalize all column names to expected keys (e.g., 'Employee ID' -> 'ee_id')
            try:
                df.rename(columns=lambda c: DataProcessingUtils.normalize_field_name(c), inplace=True)
            except Exception:
                pass
            
            # Convert name fields to strings to preserve values like "child2"
            # This ensures that even if Excel/pandas reads them as numbers, they're converted back to strings
            name_fields = ['first_name', 'middle_name', 'last_name']
            for field in name_fields:
                if field in df.columns:
                    # Convert to string, preserving the original value representation
                    df[field] = df[field].apply(
                        lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ['nan', 'none', ''] else None
                    )
            
            # Determine ee_id column after normalization
            ee_id_candidates = ['ee_id', 'employee_id', 'employee id', 'ee id', 'eeid', 'id']
            ee_id_column = next((c for c in ee_id_candidates if c in df.columns), None)
            if not ee_id_column:
                return ResponseHelper.error_response(
                    message="No valid identifier column found",
                    error="Expected one of: ee_id, employee_id, employee id, ee id, eeid, id",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Process data in batches for better performance
            batch_size = 200  # Increased batch size for better performance
            added_employees = []
            updated_employees = []
            validation_errors = []
            
            # Pre-fetch existing employees to avoid repeated queries
            existing_employee_ids = set(EmployeeDetail.objects.values_list('ee_id', flat=True))
            # Get default values once
            default_filing_status = DataProcessingUtils.get_default_filing_status()
            default_marital_status = DataProcessingUtils.get_default_marital_status()
            
            # Pre-fetch all foreign key mappings to avoid repeated queries
            from user_app.models import Client
            from processor.models import State, FedFilingStatus
            
            client_mapping = {c.client_id: c.id for c in Client.objects.all()}
            state_mapping = {str(s.state).strip().lower(): s.id for s in State.objects.all()}
            filing_status_mapping = {str(f.name).strip().lower(): f.fs_id for f in FedFilingStatus.objects.all()}
            # Process data in batches
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                
                batch_employees_to_create = []
                batch_employees_to_update = []
                
                for row_idx, row in batch_df.iterrows():
                    try:
                        # Process row data efficiently
                        employee_data = self._process_employee_row(row, default_filing_status, default_marital_status)
                        if not employee_data:
                            validation_errors.append(f"Row {batch_start + row_idx + 1}: empty row after cleaning")
                            continue
                        # Extract ee_id from the detected identifier column first
                        ee_id = row.get(ee_id_column)

                        if ee_id is None:
                            # Fallback to processed dict
                            ee_id = employee_data.get(EE.EMPLOYEE_ID)
                        # Final normalize as string to preserve prefixes/leading zeros
                        if ee_id is not None:
                            ee_id = str(ee_id).strip()
                        if not ee_id:
                            validation_errors.append(f"Row {batch_start + row_idx + 1}: missing ee_id")
                            continue
                        
                        # Check if employee exists
                        if ee_id in existing_employee_ids:
                            # Prepare for update
                            # normalize states/filing for mapping
                            if EE.HOME_STATE in employee_data and employee_data.get(EE.HOME_STATE) is not None:
                                employee_data[EE.HOME_STATE] = str(employee_data.get(EE.HOME_STATE)).strip().lower()
                            if EE.WORK_STATE in employee_data and employee_data.get(EE.WORK_STATE) is not None:
                                employee_data[EE.WORK_STATE] = str(employee_data.get(EE.WORK_STATE)).strip().lower()
                            if EE.FILING_STATUS in employee_data and employee_data.get(EE.FILING_STATUS) is not None:
                                employee_data[EE.FILING_STATUS] = str(employee_data.get(EE.FILING_STATUS)).strip().lower()
                            batch_employees_to_update.append((ee_id, employee_data))
                        else:
                            # Prepare for creation - validate required FKs before queueing
                            client_id_val = employee_data.get(EE.CLIENT_ID)


                            home_state_val = employee_data.get(EE.HOME_STATE)
                            work_state_val = employee_data.get(EE.WORK_STATE)

                            # normalize to lowercase for mapping
                            home_state_val = str(home_state_val).strip().lower() if home_state_val is not None else None
                            work_state_val = str(work_state_val).strip().lower() if work_state_val is not None else None
                            employee_data[EE.HOME_STATE] = home_state_val
                            employee_data[EE.WORK_STATE] = work_state_val

                            missing_fields = []

                            if not client_id_val:
                                missing_fields.append('client_id')
                            if not home_state_val:
                                missing_fields.append('home_state')
                            if not work_state_val:
                                missing_fields.append('work_state')
                            if missing_fields:
                                validation_errors.append(
                                    f"Row {batch_start + row_idx + 1} (ee_id={ee_id}): missing required field(s): {', '.join(missing_fields)}"
                                )
                                continue

                            mapping_missing = []
                            if client_id_val not in client_mapping:
                                mapping_missing.append(f"client_id '{client_id_val}' not found")
                            if home_state_val not in state_mapping:
                                mapping_missing.append(f"home_state '{home_state_val}' not found")
                            if work_state_val not in state_mapping:
                                mapping_missing.append(f"work_state '{work_state_val}' not found")
                            if mapping_missing:
                                validation_errors.append(
                                    f"Row {batch_start + row_idx + 1} (ee_id={ee_id}): {', '.join(mapping_missing)}"
                                )
                                continue
                            batch_employees_to_create.append((ee_id, employee_data))
                    except Exception as row_e:
                        validation_errors.append(f"Row {batch_start + row_idx + 1}: {str(row_e)}")
                        continue
                
                # Bulk create new employees and get successfully created ee_ids
                if batch_employees_to_create:
                    created_ee_ids = self._bulk_create_employees(batch_employees_to_create, client_mapping, state_mapping, filing_status_mapping)
                    added_employees.extend(created_ee_ids)
                    # Update existing_employee_ids set to include newly created employees
                    existing_employee_ids.update(created_ee_ids)
                
                # Bulk update existing employees and get successfully updated ee_ids
                if batch_employees_to_update:
                    updated_ee_ids = self._bulk_update_employees(batch_employees_to_update, client_mapping, state_mapping, filing_status_mapping)
                    updated_employees.extend(updated_ee_ids)
            
            # Build response data
            response_data = {
                "added_count": len(added_employees),
                "updated_count": len(updated_employees),
                "validation_errors_count": len(validation_errors)
            }
            
            include_all_ids = False
            try:
                include_all_ids = str(request.data.get('include_all_ids', request.query_params.get('include_all_ids', ''))).strip().lower() in ['1', 'true', 'yes']
            except Exception:
                include_all_ids = False
            
            if added_employees:
                if include_all_ids:
                    response_data["added_employees"] = added_employees
                else:
                    response_data["added_employees"] = added_employees[:50]
                    if len(added_employees) > 50:
                        response_data["added_employees_truncated"] = True
            
            if updated_employees:
                if include_all_ids:
                    response_data["updated_employees"] = updated_employees
                else:
                    response_data["updated_employees"] = updated_employees[:50]
                    if len(updated_employees) > 50:
                        response_data["updated_employees_truncated"] = True
            
            if validation_errors:
                response_data["validation_errors"] = validation_errors[:20]  # Limit error details
                if len(validation_errors) > 20:
                    response_data["validation_errors_truncated"] = True
                response_data["skipped_count"] = len(validation_errors)
            
            if not added_employees and not updated_employees:
                return ResponseHelper.error_response(
                    message="No valid data to process",
                    error=response_data,
                    status_code=status.HTTP_400_BAD_REQUEST
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
    
    def _process_employee_row(self, row, default_filing_status, default_marital_status):
        """Process a single employee row efficiently."""
        try:
            # Define date fields that need parsing

            date_fields = ["garnishment_fees_suspended_till"]

            # Address state can come from different column names depending on the file:
            # - Exported files use "address_state"
            # - Some older/manual files may use "state" → normalized to "issuing_state"
            address_state_val = row.get("address_state")
            if address_state_val is None:
                address_state_val = row.get("issuing_state")

            employee_data = {
                EE.CLIENT_ID: row.get(EE.CLIENT_ID),
                EE.FIRST_NAME: row.get(EE.FIRST_NAME),
                EE.EMPLOYEE_ID: row.get(EE.EMPLOYEE_ID),
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
                # Address fields (normalized by DataProcessingUtils.normalize_field_name)
                "address_1": row.get("address_1"),
                "address_2": row.get("address_2"),
                "zip_code": row.get("zip_code"),
                "geo_code": row.get("geo_code"),
                "city": row.get("city"),
                "address_state": address_state_val,
                "county": row.get("county"),
                "country": row.get("country"),
            }
            
            # Parse date fields using the utility function
            for date_field in date_fields:
                employee_data[date_field] = DataProcessingUtils.parse_date_field(row.get(date_field))
            
            # Clean and normalize row data using utility functions
            employee_data = DataProcessingUtils.clean_data_row(employee_data)

            # Extract address-related fields into a nested dict for easier handling later
            address_keys = [
                "address_1",
                "address_2",
                "zip_code",
                "geo_code",
                "city",
                "address_state",
                "county",
                "country",
            ]
            address_data = {}
            for key in address_keys:
                if key in employee_data and employee_data.get(key) is not None:
                    address_data[key] = employee_data.pop(key)

            if address_data:
                # Map address_state -> state to align with model/serializer field name
                if "address_state" in address_data and "state" not in address_data:
                    address_data["state"] = address_data.pop("address_state")
                employee_data["address"] = address_data
            
            # Apply basic data cleaning without strict validation
            # employee_data = DataProcessingUtils.validate_and_clean_employee_data(employee_data)
            
            # Provide default values for required fields if missing
            if not employee_data.get(EE.FILING_STATUS):
                employee_data[EE.FILING_STATUS] = default_filing_status
                
            if not employee_data.get(EE.MARITAL_STATUS):
                employee_data[EE.MARITAL_STATUS] = default_marital_status
            return employee_data
            
        except Exception as e:
            raise Exception(f"Error processing row: {str(e)}")
    
    def _bulk_create_employees(self, employees_data, client_mapping, state_mapping, filing_status_mapping):
        """Bulk create employees using bulk_create for better performance. Returns list of successfully created ee_ids."""
        if not employees_data:
            return []
            
        created_ee_ids = []
        # Track address payloads keyed by ee_id so we can create address records after employees
        addresses_by_ee_id = {}
        try:
            from django.db import transaction
            from user_app.models import Client
            
            with transaction.atomic():
                # Prepare bulk insert data
                bulk_employees = []
                for ee_id, emp_data in employees_data:
                    try:
                        # Resolve foreign keys
                        client_id = emp_data.get(EE.CLIENT_ID)
                        home_state = str(emp_data.get(EE.HOME_STATE)).strip().lower() if emp_data.get(EE.HOME_STATE) is not None else None
                        work_state = str(emp_data.get(EE.WORK_STATE)).strip().lower() if emp_data.get(EE.WORK_STATE) is not None else None
                        filing_status = str(emp_data.get(EE.FILING_STATUS)).strip().lower() if emp_data.get(EE.FILING_STATUS) is not None else None
                        
                        # Create missing client if needed
                        if client_id and client_id not in client_mapping:
                            try:
                                client = Client.objects.create(
                                    client_id=client_id,
                                    legal_name=f'Client {client_id}',
                                    is_active=True
                                )
                                client_mapping[client_id] = client.id
                            except:
                                continue  # Skip this employee if client creation fails
                        
                        # Validate required fields before creating
                        if not client_mapping.get(client_id) or not state_mapping.get(home_state) or not state_mapping.get(work_state):
                            continue  # Skip if required foreign keys are missing
                        
                        bulk_employees.append(EmployeeDetail(
                            ee_id=ee_id,  # Use the ee_id from the tuple
                            first_name=emp_data.get(EE.FIRST_NAME, ''),
                            middle_name=emp_data.get(EE.MIDDLE_NAME),
                            last_name=emp_data.get(EE.LAST_NAME),
                            client_id=client_mapping.get(client_id),
                            ssn=emp_data.get(EE.SSN, ''),
                            home_state_id=state_mapping.get(home_state),
                            work_state_id=state_mapping.get(work_state),
                            gender=emp_data.get(EE.GENDER),
                            number_of_exemptions=emp_data.get("number_of_exemptions", 0),
                            filing_status_id=filing_status_mapping.get(filing_status),
                            marital_status=emp_data.get(EE.MARITAL_STATUS, ''),
                            number_of_student_default_loan=emp_data.get("number_of_student_default_loan", 0),
                            number_of_dependent_child=emp_data.get("number_of_dependent_child", 0),
                            support_second_family=emp_data.get(EE.SUPPORT_SECOND_FAMILY, False),
                            garnishment_fees_status=emp_data.get(EE.GARNISHMENT_FEES_STATUS, False),
                            garnishment_fees_suspended_till=emp_data.get("garnishment_fees_suspended_till"),
                            number_of_active_garnishment=emp_data.get(EE.NUMBER_OF_ACTIVE_GARNISHMENT, 0),
                            status="active"
                        ))
                        created_ee_ids.append(ee_id)  # Track ee_id for successful creation

                        # Capture address data (if any) so we can create EmplopyeeAddress later
                        address_data = emp_data.get("address")
                        if address_data:
                            # Ensure we don't accidentally mutate the original dict
                            addresses_by_ee_id[ee_id] = dict(address_data)
                    except Exception as e:

                        continue  # Skip problematic records
                
                # Bulk create
                if bulk_employees:
                    EmployeeDetail.objects.bulk_create(bulk_employees, ignore_conflicts=True)

                # After employees are created, create their associated address records
                if addresses_by_ee_id:
                    employees = EmployeeDetail.objects.filter(ee_id__in=addresses_by_ee_id.keys())
                    employees_map = {emp.ee_id: emp for emp in employees}

                    address_objects = []
                    for ee_id, addr in addresses_by_ee_id.items():
                        employee = employees_map.get(ee_id)
                        if not employee:
                            continue

                        # Backward compatibility: handle address_state if present
                        addr_data = dict(addr)
                        if "address_state" in addr_data and "state" not in addr_data:
                            addr_data["state"] = addr_data.pop("address_state")

                        try:
                            address_objects.append(EmplopyeeAddress(ee=employee, **addr_data))
                        except TypeError:
                            # Skip if address payload contains unexpected keys
                            continue

                    if address_objects:
                        EmplopyeeAddress.objects.bulk_create(address_objects, ignore_conflicts=True)
                    
                return created_ee_ids
                    
        except Exception as e:

            raise Exception(f"Bulk create failed: {str(e)}")
    
    def _bulk_update_employees(self, employees_data, client_mapping, state_mapping, filing_status_mapping):
        """Bulk update employees efficiently."""
        if not employees_data:
            return
            
        try:
            from django.db import transaction
            from user_app.models import Client
            from processor.models import State, FedFilingStatus
            
            with transaction.atomic():
                # Get existing employees
                ee_ids = [emp[0] for emp in employees_data]
                existing_employees = {
                    emp.ee_id: emp for emp in EmployeeDetail.objects.filter(ee_id__in=ee_ids)
                }
                
                employees_to_update = []
                # Collect address payloads for employees that need address updates/creates
                addresses_to_upsert = []
                for ee_id, emp_data in employees_data:
                    if ee_id in existing_employees:
                        emp = existing_employees[ee_id]
                        
                        # Update fields
                        emp.first_name = emp_data.get(EE.FIRST_NAME, emp.first_name)
                        emp.middle_name = emp_data.get(EE.MIDDLE_NAME, emp.middle_name)
                        emp.last_name = emp_data.get(EE.LAST_NAME, emp.last_name)
                        emp.ssn = emp_data.get(EE.SSN, emp.ssn)
                        emp.gender = emp_data.get(EE.GENDER, emp.gender)
                        emp.number_of_exemptions = emp_data.get("number_of_exemptions", emp.number_of_exemptions)
                        emp.marital_status = emp_data.get(EE.MARITAL_STATUS, emp.marital_status)
                        emp.number_of_student_default_loan = emp_data.get("number_of_student_default_loan", emp.number_of_student_default_loan)
                        emp.number_of_dependent_child = emp_data.get("number_of_dependent_child", emp.number_of_dependent_child)
                        emp.support_second_family = emp_data.get(EE.SUPPORT_SECOND_FAMILY, emp.support_second_family)
                        emp.garnishment_fees_status = emp_data.get(EE.GARNISHMENT_FEES_STATUS, emp.garnishment_fees_status)
                        emp.garnishment_fees_suspended_till = emp_data.get("garnishment_fees_suspended_till", emp.garnishment_fees_suspended_till)
                        emp.number_of_active_garnishment = emp_data.get(EE.NUMBER_OF_ACTIVE_GARNISHMENT, emp.number_of_active_garnishment)
                        
                        # Update foreign keys if provided
                        if emp_data.get(EE.CLIENT_ID) and emp_data.get(EE.CLIENT_ID) in client_mapping:
                            emp.client_id = client_mapping[emp_data.get(EE.CLIENT_ID)]
                        home_state_key = str(emp_data.get(EE.HOME_STATE)).strip().lower() if emp_data.get(EE.HOME_STATE) is not None else None
                        work_state_key = str(emp_data.get(EE.WORK_STATE)).strip().lower() if emp_data.get(EE.WORK_STATE) is not None else None
                        filing_key = str(emp_data.get(EE.FILING_STATUS)).strip().lower() if emp_data.get(EE.FILING_STATUS) is not None else None
                        if home_state_key and home_state_key in state_mapping:
                            emp.home_state_id = state_mapping[home_state_key]
                        if work_state_key and work_state_key in state_mapping:
                            emp.work_state_id = state_mapping[work_state_key]
                        if filing_key and filing_key in filing_status_mapping:
                            emp.filing_status_id = filing_status_mapping[filing_key]
                        
                        # Capture address data (if provided) for this employee
                        address_data = emp_data.get("address")
                        if address_data:
                            addr = dict(address_data)
                            # Map address_state -> state for model compatibility
                            if "address_state" in addr and "state" not in addr:
                                addr["state"] = addr.pop("address_state")
                            addresses_to_upsert.append((emp, addr))

                        employees_to_update.append(emp)
                
                # Bulk update
                if employees_to_update:
                    EmployeeDetail.objects.bulk_update(
                        employees_to_update,
                        ['first_name', 'middle_name', 'last_name', 'ssn', 'gender', 
                         'number_of_exemptions', 'marital_status', 'number_of_student_default_loan',
                         'number_of_dependent_child', 'support_second_family', 'garnishment_fees_status',
                         'garnishment_fees_suspended_till', 'number_of_active_garnishment', 'client_id',
                         'home_state_id', 'work_state_id', 'filing_status_id', 'updated_at']
                    )

                # Upsert address records for updated employees
                for emp, addr in addresses_to_upsert:
                    try:

                        address_obj, created = EmplopyeeAddress.objects.get_or_create(
                            ee=emp,
                            defaults=addr,
                        )
                        if not created:
                            for field, value in addr.items():
                                setattr(address_obj, field, value)
                            address_obj.save()
                    except Exception:
                        # Skip address update errors to avoid failing the whole batch
                        continue
            return [emp.ee_id for emp in employees_to_update]

        except Exception as e:
            raise Exception(f"Bulk update failed: {str(e)}")




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
                # Optimized fetch: avoid N+1 by selecting related objects and limiting columns
                queryset = (
                    EmployeeDetail.objects
                    .select_related('client', 'home_state', 'work_state', 'filing_status')
                    .only(
                        'id', 'ee_id',
                        'client__client_id',
                        'first_name', 'middle_name', 'last_name',
                        'ssn',
                        'home_state__state', 'work_state__state',
                        'gender', 'number_of_exemptions',
                        'filing_status__name',
                        'marital_status', 'number_of_student_default_loan',
                        'number_of_dependent_child', 'support_second_family',
                        'garnishment_fees_status', 'garnishment_fees_suspended_till',
                        'number_of_active_garnishment', 'status',
                        'created_at', 'updated_at'
                    )
                    .order_by('id')
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
                    serializer = EmployeeDetailsSerializer(page_obj.object_list, many=True)
                    return ResponseHelper.success_response(
                        'Page fetched successfully',
                        {
                            'results': serializer.data,
                            'page': page,
                            'page_size': page_size,
                            'total_pages': paginator.num_pages,
                            'total_items': paginator.count,
                        }
                    )
                except (ValueError, EmptyPage):
                    return ResponseHelper.error_response(
                        'Invalid page or page_size',
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
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
    @audit_api_call
    @audit_business_operation("employee_list_retrieval")
    @audit_data_access("EmployeeDetail", "READ")
    def get(self, request):
        """
        Get paginated list of active employees.
        """
        try:
            # Optimized queryset to avoid N+1 and reduce columns
            queryset = (
                EmployeeDetail.objects
                .select_related('client', 'home_state', 'work_state', 'filing_status')
                .only(
                    'id', 'ee_id',
                    'client__client_id',
                    'first_name', 'middle_name', 'last_name',
                    'ssn',
                    'home_state__state', 'work_state__state',
                    'gender', 'number_of_exemptions',
                    'filing_status__name',
                    'marital_status', 'number_of_student_default_loan',
                    'number_of_dependent_child', 'support_second_family',
                    'garnishment_fees_status', 'garnishment_fees_suspended_till',
                    'number_of_active_garnishment', 'status',
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
                serializer = EmployeeDetailsSerializer(page_obj.object_list, many=True)
                return ResponseHelper.success_response(
                    message="Employees fetched successfully",
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
            employee.status = "inactive"
            employee.save(update_fields=["status"])
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


class ExportEmployeeDataView(APIView):
    """
    Exports employee details as an Excel file.
    Includes address fields in the export.
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
            employees = EmployeeDetail.objects.select_related('client', 'home_state', 'work_state', 'filing_status').prefetch_related('employee_addresses').all()
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

            # Define headers including address fields
            header_fields = [
                EE.EMPLOYEE_ID, EE.SSN, EE.CLIENT_ID, EE.FIRST_NAME, EE.MIDDLE_NAME, EE.LAST_NAME, 
                EE.GENDER, EE.HOME_STATE, EE.WORK_STATE, EE.MARITAL_STATUS, EE.FILING_STATUS,
                'number_of_exemptions', EE.SUPPORT_SECOND_FAMILY, 'number_of_dependent_child',
                'number_of_student_default_loan', EE.GARNISHMENT_FEES_STATUS, 
                EE.GARNISHMENT_FEES_SUSPENDED_TILL, EE.NUMBER_OF_ACTIVE_GARNISHMENT, 
                CF.STATUS, CF.CREATED_AT, CF.UPDATED_AT,
                # Address fields
                'address_1', 'address_2', 'zip_code', 'geo_code', 'city', 'address_state', 'county', 'country'
            ]
            ws.append(header_fields)

            # Append employee data
            for employee in serializer.data:
                row = []
                # Employee fields
                for field in header_fields[:20]:  # First 20 fields are employee fields
                    row.append(employee.get(field, ''))
                
                # Address fields
                address = employee.get('address', {}) if employee.get('address') else {}
                row.append(address.get('address_1', ''))
                row.append(address.get('address_2', ''))
                row.append(address.get('zip_code', ''))
                row.append(address.get('geo_code', ''))
                row.append(address.get('city', ''))
                row.append(address.get('state', ''))
                row.append(address.get('county', ''))
                row.append(address.get('country', ''))
                
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
