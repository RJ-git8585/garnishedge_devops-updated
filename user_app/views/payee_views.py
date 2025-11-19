from user_app.models import PayeeDetails, PayeeAddress
from processor.models.shared_model.state import State
from processor.garnishment_library.utils.response import ResponseHelper
import logging
from django.core.exceptions import ValidationError
from user_app.serializers import PayeeSerializer
from user_app.models import GarnishmentOrder
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import pandas as pd
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage

logger = logging.getLogger(__name__)

# CRUD operations on Payee (SDU) using id
class PayeeByIDAPIView(APIView):
    """
    API view for CRUD operations on SDU using id.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Payee fetched successfully', PayeeSerializer),
            404: 'Payee not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, id=None):
        """
        Retrieve payee data by id or all payees if not provided.
        """
        try:
            if id:
                try:
                    # Lookup by primary key `id`; response includes `payee_id` field
                    # Optimize query with select_related to avoid N+1 queries
                    payee = PayeeDetails.objects.select_related(
                        'state',           # PayeeDetails.state ForeignKey
                        'address',          # PayeeAddress OneToOne relationship
                        'address__state'    # PayeeAddress.state ForeignKey
                    ).get(id=id)
                    serializer = PayeeSerializer(payee)
                    return ResponseHelper.success_response(
                        f'Payee with id "{id}" fetched successfully', serializer.data
                    )
                except PayeeDetails.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'Payee with id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Optimized fetch: avoid N+1 by selecting related objects and limiting columns
                # Similar to EmployeeDetailsAPIViews for consistent performance
                queryset = (
                    PayeeDetails.objects
                    .select_related(
                        'state',           # PayeeDetails.state ForeignKey
                        'address',          # PayeeAddress OneToOne relationship
                        'address__state'   # PayeeAddress.state ForeignKey
                    )
                    .only(
                        'id', 'payee_id', 'payee_type', 'payee',
                        'routing_number', 'bank_account',
                        'case_number_required', 'case_number_format',
                        'fips_required', 'fips_length',
                        'last_used', 'status',
                        'created_at', 'updated_at',
                        # State fields
                        'state__id', 'state__state', 'state__state_code',
                        # Address fields
                        'address__id', 'address__address_1', 'address__address_2',
                        'address__city', 'address__zip_code', 'address__zip_plus_4',
                        # Address state fields
                        'address__state__id', 'address__state__state', 'address__state__state_code'
                    )
                    .order_by('id')
                )

                # Chunked pagination (defaults if not provided)
                page = request.query_params.get('page') or 1
                page_size = request.query_params.get('page_size') or 500
                try:
                    page = int(page)
                    page_size = max(1, min(1000, int(page_size)))
                    paginator = Paginator(queryset, page_size)
                    page_obj = paginator.page(page)
                    serializer = PayeeSerializer(page_obj.object_list, many=True)
                    return ResponseHelper.success_response(
                        'All payees fetched successfully',
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
            logger.exception("Unexpected error in GET method of PayeeByIDAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch payee data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, id=None):
        """
        Create a new payee.
        """
        try:
            serializer = PayeeSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Payee created successfully', serializer.data, status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Unexpected error in POST method of PayeeByIDAPIView")
            return ResponseHelper.error_response(
                'Internal server error while creating payee', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=PayeeSerializer,
        responses={
            200: openapi.Response('Payee updated successfully', PayeeSerializer),
            400: 'id is required in URL or invalid data',
            404: 'Payee not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, id=None):
        """
        Update payee data for a specific id.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to update payee', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            # Lookup by primary key `id`; request/response body can include `payee_id`
            payee = PayeeDetails.objects.get(id=id)
        except PayeeDetails.DoesNotExist:
            return ResponseHelper.error_response(f'Payee with id \"{id}\" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = PayeeSerializer(payee, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Payee updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating payee")
            return ResponseHelper.error_response(
                'Internal server error while updating payee', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'Payee deleted successfully',
            400: 'id is required in URL to delete payee',
            404: 'Payee not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, id=None):
        """
        Delete payee data for a specific id.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to delete payee', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            # Lookup by primary key `id`; `payee_id` remains as data field
            payee = PayeeDetails.objects.get(id=id)
            payee.delete()
            return ResponseHelper.success_response(f'Payee with id "{id}" deleted successfully')
        except PayeeDetails.DoesNotExist:
            return ResponseHelper.error_response(f'Payee with id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in DELETE method of PayeeByIDAPIView")
            return ResponseHelper.error_response(
                'Internal server error while deleting payee', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
# Get payee by state name or abbreviation
class PayeeByStateAPIView(APIView):
    """
    API view to get payee(s) by state name or abbreviation using the `PayeeDetails.state` relation.
    """
    @swagger_auto_schema(
        responses={
            200: openapi.Response('Payees for state fetched successfully', PayeeSerializer(many=True)),
            404: 'No payees found for state',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, state=None):
        """
        Retrieve payee(s) for a specific state name or abbreviation.
        """
        if not state:
            return ResponseHelper.error_response('State is required in URL to fetch payees', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            normalized_state = state.strip()
            # Filter payees by related `State` name or abbreviation (case-insensitive)
            # Optimize query with select_related to avoid N+1 queries
            payees = PayeeDetails.objects.select_related(
                'state',           # PayeeDetails.state ForeignKey
                'address',          # PayeeAddress OneToOne relationship
                'address__state'    # PayeeAddress.state ForeignKey
            ).filter(
                state__state__iexact=normalized_state
            ) | PayeeDetails.objects.select_related(
                'state',
                'address',
                'address__state'
            ).filter(
                state__state_code__iexact=normalized_state
            )
            payees = payees.distinct()
            if not payees.exists():
                return ResponseHelper.error_response(f'No payees found for state "{state}"', status_code=status.HTTP_404_NOT_FOUND)
            serializer = PayeeSerializer(payees, many=True)
            return ResponseHelper.success_response(
                f'Payees for state "{state}" fetched successfully', serializer.data
            )
        except Exception as e:
            logger.exception("Unexpected error in GET method of PayeeByStateAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch payee data for state', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PayeeImportView(APIView):
    """
    API view to handle the import (upsert) of payees from a file.
    Updates existing payees by combination of `case_id` and `payee` (and implicitly state), or creates new ones.
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
            # Use converters/dtype to force payee_id and case_id as strings to preserve alphanumeric values
            # Excel often converts "G3288" to 3288, so we need to read these columns as strings
            if file_name.endswith('.csv'):
                # For CSV, specify dtype for specific columns
                df = pd.read_csv(file, dtype={'payee_id': str, 'case_id': str}, na_values=[''])
            elif file_name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb', '.odf', '.ods', '.odt')):
                # For Excel, use converters to force string conversion at read time
                # This preserves alphanumeric values like "G3288" if stored as text in Excel
                # Note: If Excel has already converted "G3288" to 3288 (stored as number), 
                # we can't recover the "G" prefix - it will be read as "3288" (string)
                # pandas will ignore converters for columns that don't exist, so it's safe to always include them
                converters = {
                    'payee_id': str,
                    'case_id': str
                }
                # Read the full file with converters
                df = pd.read_excel(file, converters=converters)
            else:
                return ResponseHelper.error_response(
                    message="Unsupported file format. Please upload a CSV or Excel file.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Additional safety: Convert payee_id and case_id columns to string if they exist
            # This handles edge cases and ensures consistent string type
            if 'payee_id' in df.columns:
                df['payee_id'] = df['payee_id'].astype(str)
                # Replace pandas NaN string representations with empty string
                df['payee_id'] = df['payee_id'].replace(['nan', 'None', 'NaN', 'NAT', 'NaT'], '')
            if 'case_id' in df.columns:
                df['case_id'] = df['case_id'].astype(str)
                df['case_id'] = df['case_id'].replace(['nan', 'None', 'NaN', 'NAT', 'NaT'], '')

            # Convert dataframe to list of dicts once (faster than iterrows)
            records = df.to_dict(orient="records")

            # Pre-fetch all states into dictionaries for O(1) lookup (supports both name and code)
            all_states = State.objects.all()
            state_by_name = {state.state.lower(): state for state in all_states if state.state}
            state_by_code = {state.state_code.lower(): state for state in all_states if state.state_code}
            
            def get_state(state_value):
                """Helper to get State instance from name or code (case-insensitive)"""
                if not state_value or pd.isna(state_value):
                    return None
                normalized = str(state_value).strip().lower()
                # Also check for string 'nan' which can come from Excel/CSV
                if normalized == 'nan' or normalized == '':
                    return None
                return state_by_name.get(normalized) or state_by_code.get(normalized)
            
            def clean_numeric_value(value):
                """Helper to convert NaN values to None for numeric fields (BigIntegerField supports large numbers)"""
                if value is None:
                    return None
                # Check for pandas NaN
                try:
                    if pd.isna(value):
                        return None
                except (TypeError, ValueError):
                    pass
                # Also check for string 'nan'
                if isinstance(value, str):
                    value = value.strip()
                    if value == '' or value.lower() == 'nan':
                        return None
                    try:
                        # Try to convert to int (remove decimal part if float string)
                        if '.' in value:
                            float_val = float(value)
                            if pd.isna(float_val):
                                return None
                            return int(float_val)
                        return int(value)
                    except (ValueError, TypeError, OverflowError):
                        return None
                # If it's already a number, convert to int
                if isinstance(value, (int, float)):
                    try:
                        if pd.isna(value):
                            return None
                    except (TypeError, ValueError):
                        pass
                    try:
                        return int(value)
                    except (OverflowError, ValueError, TypeError):
                        return None
                return None

            # Prefetch existing payees and orders in bulk to avoid per-row queries
            payee_ids_in_file = {
                (r.get("payee_id") or "").strip()
                for r in records
                if r.get("payee_id")
            }
            case_ids_in_file = {
                (r.get("case_id") or "").strip()
                for r in records
                if r.get("case_id")
            }

            existing_payees_by_payee_id = {
                p.payee_id: p
                for p in PayeeDetails.objects.filter(payee_id__in=payee_ids_in_file).select_related('state')
            }

            orders_by_case_id = {
                o.case_id: o
                for o in GarnishmentOrder.objects.filter(case_id__in=case_ids_in_file).select_related("payee", "payee__state")
            }
            
            # Process all records in memory first
            payees_to_create = []
            payees_to_update = []
            addresses_to_create = []
            addresses_to_update = []
            added_payees = []
            updated_payees = []
            validation_errors = []
            
            for row_idx, row in enumerate(records, start=1):
                try:
                    # Extract identifiers
                    payee_id_val = (row.get("payee_id") or "").strip()
                    raw_case_id = row.get("case_id")
                    case_id = (raw_case_id or "").strip() if raw_case_id is not None else ""

                    # Require at least one identifier
                    if not payee_id_val and not case_id:
                        continue
                    
                    # Find existing payee
                    existing_payee = None
                    if payee_id_val:
                        existing_payee = existing_payees_by_payee_id.get(payee_id_val)
                    else:
                        order = orders_by_case_id.get(case_id)
                        existing_payee = order.payee if order and order.payee else None
                    
                    sdu_identifier = f"{payee_id_val or case_id}_{row.get('payee', 'unknown')}"
                    
                    # Handle state lookup (supports both name and abbreviation)
                    state_value = row.get("state")
                    # Check for NaN values
                    if pd.isna(state_value) or (isinstance(state_value, str) and state_value.strip().lower() == 'nan'):
                        validation_errors.append(f"Row {row_idx}: State is missing or invalid (NaN)")
                        continue
                    state_instance = get_state(state_value)
                    if state_value and not state_instance:
                        validation_errors.append(f"Row {row_idx}: State '{state_value}' not found (neither by name nor code)")
                        continue
                    
                    # Handle last_used date conversion
                    last_used = row.get("last_used")
                    if last_used:
                        try:
                            if isinstance(last_used, str):
                                last_used = pd.to_datetime(last_used).date()
                            elif hasattr(last_used, 'date'):
                                last_used = last_used.date()
                        except (ValueError, AttributeError):
                            last_used = None
                    
                    # Handle fips_length with range validation
                    MAX_INT = 2147483647
                    MIN_INT = -2147483648
                    raw_fips = row.get("fips_length")
                    fips_length = None
                    if raw_fips is not None and not pd.isna(raw_fips):
                        try:
                            if isinstance(raw_fips, (int, float)) and not isinstance(raw_fips, bool):
                                fips_int = int(raw_fips)
                                if fips_int > MAX_INT or fips_int < MIN_INT:
                                    validation_errors.append(f"Row {row_idx}: 'fips_length' value {raw_fips} is out of range (must be between {MIN_INT} and {MAX_INT})")
                                    continue
                                fips_length = fips_int
                            elif isinstance(raw_fips, str):
                                s = raw_fips.strip()
                                if s and s.lower() != 'nan' and s.isdigit():
                                    fips_int = int(s)
                                    if fips_int > MAX_INT or fips_int < MIN_INT:
                                        validation_errors.append(f"Row {row_idx}: 'fips_length' value {raw_fips} is out of range (must be between {MIN_INT} and {MAX_INT})")
                                        continue
                                    fips_length = fips_int
                        except (ValueError, TypeError, OverflowError):
                            pass  # Invalid value, will remain None
                    
                    # Validate required fields before processing
                    if not payee_id_val and not case_id:
                        continue
                    if not row.get("payee"):
                        validation_errors.append(f"Row {row_idx}: 'payee' field is required")
                        continue
                    if not state_instance:
                        validation_errors.append(f"Row {row_idx}: Valid state is required")
                        continue
                    
                    # For new payees, payee_id is required
                    if not existing_payee and not payee_id_val:
                        validation_errors.append(f"Row {row_idx}: 'payee_id' is required for new payees")
                        continue
                    
                    # Prepare payee data
                    payee_data = {
                        "payee_id": payee_id_val,
                        "payee_type": row.get("payee_type"),
                        "payee": row.get("payee"),
                        "routing_number": clean_numeric_value(row.get("routing_number")),
                        "bank_account": clean_numeric_value(row.get("bank_account")),
                        "case_number_required": bool(row.get("case_number_required", False)),
                        "case_number_format": row.get("case_number_format"),
                        "fips_required": bool(row.get("fips_required", False)),
                        "fips_length": fips_length,
                        "last_used": last_used,
                        "status": row.get("status"),
                        "state": state_instance,
                    }
                    
                    # Remove None values (except for boolean fields, required fields, and nullable numeric fields)
                    # Keep nullable numeric fields (routing_number, bank_account) even if None to allow explicit NULL setting
                    payee_data = {k: v for k, v in payee_data.items() if v is not None or k in ['case_number_required', 'fips_required', 'payee_id', 'payee', 'state', 'routing_number', 'bank_account']}
                    
                    # Prepare address data if present
                    address_data = None
                    if any(row.get(field) for field in ['address_1', 'address_2', 'city', 'state', 'zip_code', 'zip_plus_4']):
                        address_state = get_state(state_value)  # Use same state lookup
                        if address_state:
                            # Clean zip_code and zip_plus_4 to handle NaN values
                            zip_code_val = clean_numeric_value(row.get("zip_code"))
                            zip_plus_4_val = clean_numeric_value(row.get("zip_plus_4"))
                            
                            address_data = {
                                "address_1": row.get("address_1"),
                                "address_2": row.get("address_2"),
                                "city": row.get("city"),
                                "state": address_state,
                                "zip_code": zip_code_val,
                                "zip_plus_4": zip_plus_4_val,
                            }
                            # Remove None values
                            address_data = {k: v for k, v in address_data.items() if v is not None}
                            if not address_data:
                                address_data = None
                    
                    if existing_payee:
                        # Update existing payee
                        for attr, value in payee_data.items():
                            setattr(existing_payee, attr, value)
                        payees_to_update.append(existing_payee)
                        updated_payees.append(sdu_identifier)
                        
                        # Handle address update/create
                        if address_data:
                            address_data['payee'] = existing_payee
                            addresses_to_update.append((existing_payee, address_data))
                    else:
                        # Create new payee
                        new_payee = PayeeDetails(**payee_data)
                        payees_to_create.append(new_payee)
                        added_payees.append(sdu_identifier)
                        
                        # Store address data for later creation
                        if address_data:
                            addresses_to_create.append((new_payee, address_data))
                            
                except Exception as row_e:
                    logger.exception(f"Error processing payee row {row_idx}: {str(row_e)}")
                    validation_errors.append(f"Row {row_idx}: {str(row_e)}")
                    continue  # Skip this row and continue processing other rows
            
            # Perform bulk operations in a transaction (even if there are validation errors)
            try:
                with transaction.atomic():
                    # Bulk create new payees
                    if payees_to_create:
                        PayeeDetails.objects.bulk_create(payees_to_create, ignore_conflicts=False)
                        # After bulk_create, Django sets the IDs on the objects
                        # Create addresses for new payees using bulk_create
                        if addresses_to_create:
                            address_objects = [
                                PayeeAddress(payee=payee, **addr_data)
                                for payee, addr_data in addresses_to_create
                            ]
                            PayeeAddress.objects.bulk_create(address_objects, ignore_conflicts=False)
                    
                    # Bulk update existing payees
                    if payees_to_update:
                        PayeeDetails.objects.bulk_update(
                            payees_to_update,
                            ['payee_type', 'payee', 'routing_number', 'bank_account', 
                             'case_number_required', 'case_number_format', 'fips_required', 
                             'fips_length', 'last_used', 'status', 'state', 'updated_at']
                        )
                    # For OneToOne relationships, we need to handle updates individually
                    # but we can batch the lookups
                    if addresses_to_update:
                        payee_ids = [payee.id for payee, _ in addresses_to_update]
                        existing_addresses = {
                            addr.payee_id: addr
                            for addr in PayeeAddress.objects.filter(payee_id__in=payee_ids)
                        }
                        
                        addresses_to_bulk_create = []
                        addresses_to_bulk_update = []
                        
                        for payee, addr_data in addresses_to_update:
                            if payee.id in existing_addresses:
                                # Update existing address
                                addr = existing_addresses[payee.id]
                                for attr, value in addr_data.items():
                                    setattr(addr, attr, value)
                                addresses_to_bulk_update.append(addr)
                            else:
                                # Create new address
                                addresses_to_bulk_create.append(
                                    PayeeAddress(payee=payee, **addr_data)
                                )
                        
                        if addresses_to_bulk_create:
                            PayeeAddress.objects.bulk_create(addresses_to_bulk_create, ignore_conflicts=False)
                        if addresses_to_bulk_update:
                            PayeeAddress.objects.bulk_update(
                                addresses_to_bulk_update,
                                ['address_1', 'address_2', 'city', 'state', 'zip_code', 'zip_plus_4']
                            )
            except Exception as db_error:
                # Catch database errors and add to validation errors
                error_msg = str(db_error)
                if "integer out of range" in error_msg.lower() or "overflow" in error_msg.lower():
                    # This could be fips_length or other integer fields
                    validation_errors.append(f"Database error: Integer value out of range. Please check numeric fields (must be between -2147483648 and 2147483647)")
                else:
                    validation_errors.append(f"Database error: {error_msg}")
                logger.exception(f"Error during bulk database operations: {str(db_error)}")
                # Clear the lists since the operation failed
                payees_to_create = []
                payees_to_update = []
                added_payees = []
                updated_payees = []

            # Build response data
            response_data = {}
            
            if added_payees:
                response_data["added_payees"] = added_payees
                response_data["added_count"] = len(added_payees)
            
            if updated_payees:
                response_data["updated_payees"] = updated_payees
                response_data["updated_count"] = len(updated_payees)
            
            # Include validation errors in response if any
            if validation_errors:
                response_data["validation_errors"] = validation_errors
                response_data["error_count"] = len(validation_errors)
            
            # Determine response message and status
            if not added_payees and not updated_payees:
                if validation_errors:
                    # All rows had errors
                    return ResponseHelper.error_response(
                        message="No valid payee data to process. All rows had validation errors.",
                        error=validation_errors,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    return ResponseHelper.success_response(
                        message="No valid payee data to process",
                        data=response_data,
                        status_code=status.HTTP_200_OK
                    )
            
            # Some or all rows were processed successfully
            if validation_errors:
                message = f"File processed with {len(validation_errors)} validation error(s). {len(added_payees) + len(updated_payees)} row(s) processed successfully."
            else:
                message = "File processed successfully"
            
            return ResponseHelper.success_response(
                message=message,
                data=response_data,
                status_code=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.exception(f"Error importing payee: {str(e)}")
            return ResponseHelper.error_response(
                message="Failed to import payee",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportPayeeDataView(APIView):
    """
    API view to export payee data as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    @swagger_auto_schema(
        responses={
            200: 'Excel file exported successfully',
            404: 'No payees found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Handles GET request to export all payees to an Excel file.
        """
        try:
            # Fetch all payees from the database
            # Optimize query with select_related to avoid N+1 queries
            payees = PayeeDetails.objects.select_related(
                'state',           # PayeeDetails.state ForeignKey
                'address',          # PayeeAddress OneToOne relationship
                'address__state'    # PayeeAddress.state ForeignKey
            ).all()
            if not payees.exists():
                return ResponseHelper.error_response(
                    message="No payees found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = PayeeSerializer(payees, many=True)

            # Create Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "payees"

            # Define header fields - include all PayeeDetails fields and address fields
            header_fields = [
                "id", "payee_id", "payee_type", "payee", "case_id",
                "routing_number", "bank_account", "case_number_required",
                "case_number_format", "fips_required", "fips_length",
                "last_used", "status", "state", "created_at", "updated_at",
                "address_1", "address_2", "city", "zip_code", "zip_plus_4"
            ]

            ws.append(header_fields)

            # Write data rows to the worksheet
            for payee in serializer.data:
                row_data = []
                for field in header_fields:
                    if field in ['address_1', 'address_2', 'city', 'zip_code', 'zip_plus_4']:
                        # Extract from nested address object
                        address = payee.get('address', {}) or {}
                        row_data.append(address.get(field, ''))
                    else:
                        row_data.append(payee.get(field, ''))
                ws.append(row_data)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'payees_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.exception(f"Error exporting payee data: {str(e)}")
            return ResponseHelper.error_response(
                message="Failed to export payee data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )