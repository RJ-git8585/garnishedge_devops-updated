import hashlib
import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Any, Optional, Union

class HashValue:
    """Utility class for hashing values."""

    @staticmethod
    def hash_value(value: str) -> str:
        """Return a SHA-256 hash for the given value."""
        if value:
            return hashlib.sha256(value.encode('utf-8')).hexdigest()
        return None


class DataProcessingUtils:
    """Utility class for data processing operations."""

    @staticmethod
    def clean_nan_values(value: Any) -> Any:
        """
        Clean NaN values from any data type to make it JSON serializable.
        
        Args:
            value: Any value that might contain NaN
            
        Returns:
            Any: Cleaned value safe for JSON serialization
        """
        if value is None:
            return None
        
        # Handle pandas NaN
        if pd.isna(value):
            return None
        
        # Handle numpy NaN
        if isinstance(value, (np.floating, np.integer)):
            if np.isnan(value) if isinstance(value, np.floating) else False:
                return None
            return value.item() if hasattr(value, 'item') else value
        
        # Handle float NaN
        if isinstance(value, float) and (np.isnan(value) or str(value).lower() == 'nan'):
            return None
        
        # Handle string representations of NaN
        if isinstance(value, str) and value.lower() in ['nan', 'null', 'none', '']:
            return None
        
        return value

    @staticmethod
    def make_json_safe(data: Any) -> Any:
        """
        Recursively clean data to make it JSON serializable.
        
        Args:
            data: Data structure to clean
            
        Returns:
            Any: JSON-safe data structure
        """
        if isinstance(data, dict):
            return {key: DataProcessingUtils.make_json_safe(value) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [DataProcessingUtils.make_json_safe(item) for item in data]
        elif isinstance(data, (pd.Series, pd.DataFrame)):
            # Convert pandas objects to native Python types
            if isinstance(data, pd.Series):
                return [DataProcessingUtils.clean_nan_values(item) for item in data.tolist()]
            else:
                return data.to_dict('records')
        else:
            return DataProcessingUtils.clean_nan_values(data)

    @staticmethod
    def parse_date_field(date_value: Any) -> Optional[str]:
        """
        Parse various date formats and return YYYY-MM-DD format string.
        
        Args:
            date_value: Date value in any supported format
            
        Returns:
            str: Date in YYYY-MM-DD format or None if invalid
        """
        # Clean NaN values first
        date_value = DataProcessingUtils.clean_nan_values(date_value)
        
        if date_value is None or date_value == '' or str(date_value).strip() == '':
            return None
        
        try:
            # Convert to string and strip whitespace
            date_str = str(date_value).strip()
            
            # Handle common null representations
            if date_str.lower() in ['', 'nan', 'null', 'none', 'n/a', 'na']:
                return None
            
            # If already a datetime object, format it
            if isinstance(date_value, datetime):
                return date_value.strftime("%Y-%m-%d")
            
            # List of supported date formats
            date_formats = [
                '%m-%d-%Y',      # MM-DD-YYYY
                '%Y-%m-%d',      # YYYY-MM-DD
                '%m/%d/%Y',      # MM/DD/YYYY
                '%Y/%m/%d',      # YYYY/MM/DD
                '%m-%d-%y',      # MM-DD-YY
                '%y-%m-%d',      # YY-MM-DD
                '%m/%d/%y',      # MM/DD/YY
                '%y/%m/%d',      # YY/MM/DD
                '%d-%m-%Y',      # DD-MM-YYYY
                '%d/%m/%Y',      # DD/MM/YYYY
                '%d-%m-%y',      # DD-MM-YY
                '%d/%m/%y',      # DD/MM/YY
                '%Y.%m.%d',      # YYYY.MM.DD
                '%m.%d.%Y',      # MM.DD.YYYY
                '%d.%m.%Y',      # DD.MM.YYYY
            ]
            
            # Try each format
            for date_format in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, date_format)
                    return date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            
            # Try pandas parsing as fallback
            try:
                parsed_date = pd.to_datetime(date_str, errors='coerce')
                if not pd.isnull(parsed_date):
                    return parsed_date.strftime("%Y-%m-%d")
            except Exception:
                pass
            
            return None
            
        except Exception:
            return None

    @staticmethod
    def parse_integer_field(int_value: Any) -> Optional[int]:
        """
        Parse various integer formats and return clean integer value.
        
        Args:
            int_value: Integer value in any supported format
            
        Returns:
            int: Clean integer value or None if invalid
        """
        # Clean NaN values first
        int_value = DataProcessingUtils.clean_nan_values(int_value)
        
        if int_value is None or str(int_value).strip() == '':
            return None
        
        try:
            # Convert to string and strip whitespace
            val_str = str(int_value).strip()
            
            # Handle common null representations
            if val_str.lower() in ['', 'nan', 'null', 'none', 'n/a', 'na']:
                return None
            
            # Remove any non-numeric characters except minus sign
            cleaned_val = re.sub(r'[^\d-]', '', val_str)
            
            # Handle empty string after cleaning
            if cleaned_val == '' or cleaned_val == '-':
                return None
            
            # Convert to integer
            return int(cleaned_val)
            
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_string_field(str_value: Any) -> Optional[str]:
        """
        Parse and normalize a string field while preserving non-numeric prefixes
        and leading zeros (e.g., 'D00500' stays 'D00500').

        Args:
            str_value: Value to coerce to a clean string

        Returns:
            str: Trimmed string or None if empty/invalid
        """
        # Clean NaN values first
        str_value = DataProcessingUtils.clean_nan_values(str_value)

        if str_value is None:
            return None

        try:
            # Already string → trim
            if isinstance(str_value, str):
                cleaned = str_value.strip()
                return cleaned if cleaned != '' else None

            # For numeric types, convert to string without losing leading zeros for known formats
            # Since we cannot infer formatting from numeric types, simply cast to string
            # to avoid unintended integer coercion.
            cleaned = str(str_value).strip()
            return cleaned if cleaned != '' else None
        except Exception:
            return None

    @staticmethod
    def parse_boolean_field(bool_value: Any) -> Optional[bool]:
        """
        Parse various boolean formats and return clean boolean value.
        
        Args:
            bool_value: Boolean value in any supported format
            
        Returns:
            bool: Clean boolean value or None if invalid
        """
        # Clean NaN values first
        bool_value = DataProcessingUtils.clean_nan_values(bool_value)
        
        if bool_value is None or str(bool_value).strip() == '':
            return None
        
        try:
            # Convert to string and strip whitespace
            val_str = str(bool_value).strip().lower()
            
            # Handle common null representations
            if val_str in ['', 'nan', 'null', 'none', 'n/a', 'na']:
                return None
            
            # Handle string representations
            if val_str in ['true', '1', 'yes', 'y', 'on', 'enabled']:
                return True
            elif val_str in ['false', '0', 'no', 'n', 'off', 'disabled']:
                return False
            elif val_str in ['true', 'false']:  # Handle Excel boolean strings
                return val_str == 'true'
            
            # Handle numeric values
            if isinstance(bool_value, (int, float)):
                return bool(bool_value)
            
            return None
            
        except Exception:
            return None

    @staticmethod
    def normalize_field_name(field_name: str) -> str:
        """
        Normalize field names to handle variations in Excel column names.
        
        Args:
            field_name: Original field name from Excel/CSV
            
        Returns:
            str: Normalized field name
        """
        if not field_name:
            return field_name
        
        # Convert to lowercase and strip whitespace
        normalized = str(field_name).strip().lower()
        
        # Handle common variations
        field_mappings = {
            'filing status': 'filing_status',
            'filingstatus': 'filing_status',
            'marital status': 'marital_status',
            'maritalstatus': 'marital_status',
            'client id': 'client_id',
            'clientid': 'client_id',
            'employee id': 'ee_id',
            'employeeid': 'ee_id',
            'ee id': 'ee_id',
            'eeid': 'ee_id',
            'first name': 'first_name',
            'firstname': 'first_name',
            'last name': 'last_name',
            'lastname': 'last_name',
            'middle name': 'middle_name',
            'middlename': 'middle_name',
            'home state': 'home_state',
            'homestate': 'home_state',
            'work state': 'work_state',
            'workstate': 'work_state',
            'issuing state': 'issuing_state',
            'issuingstate': 'issuing_state',
            'state': 'issuing_state',  # Common default for issuing_state
            'social security number': 'ssn',
            'ssn': 'ssn',
            'case id': 'case_id',
            'caseid': 'case_id',
            'garnishment type': 'garnishment_type',
            'garnishmenttype': 'garnishment_type',
            'type': 'garnishment_type',
            'ftb_order': 'ftb_order',  # Handle FTB_Order variant
            'ftborder': 'ftb_order'   ,
            'number of exemptions': 'number_of_exemptions',
            'numberofexemptions': 'number_of_exemptions',
            'number of exemption': 'number_of_exemptions',  # Handle singular form
            'numberofexemption': 'number_of_exemptions',
            'number of dependent child': 'number_of_dependent_child',
            'numberofdependentchild': 'number_of_dependent_child',
            'number of student default loan': 'number_of_student_default_loan',
            'numberofstudentdefaultloan': 'number_of_student_default_loan',
            'number of student default loa': 'number_of_student_default_loan',  # Handle truncated
            'support second family': 'support_second_family',
            'supportsecondfamily': 'support_second_family',
            'garnishment fees status': 'garnishment_fees_status',
            'garnishmentfeesstatus': 'garnishment_fees_status',
            'garnishment fees suspended till': 'garnishment_fees_suspended_till',
            'garnishmentfeessuspendedtill': 'garnishment_fees_suspended_till',
            'number of active garnishment': 'number_of_active_garnishment',
            'numberofactivegarnishment': 'number_of_active_garnishment',
            # Handle the complex concatenated field name
            'number of acgarnishment fees suspended tisupport secondgarnishment fe': 'garnishment_fees_suspended_till',
            # Address field mappings
            'address 1': 'address_1',
            'address1': 'address_1',
            'address line 1': 'address_1',
            'addressline1': 'address_1',
            'address 2': 'address_2',
            'address2': 'address_2',
            'address line 2': 'address_2',
            'addressline2': 'address_2',
            'zip code': 'zip_code',
            'zipcode': 'zip_code',
            'postal code': 'zip_code',
            'postalcode': 'zip_code',
            'zip': 'zip_code',
            'geo code': 'geo_code',
            'geocode': 'geo_code',
            'city': 'city',
            'address state': 'address_state',
            'addressstate': 'address_state',
            'state address': 'address_state',
            'county': 'county',
            'country': 'country',
        }

        # Return mapped value if known, otherwise the normalized key
        return field_mappings.get(normalized, normalized)

    @staticmethod
    def clean_data_row(row_data: dict) -> dict:
        """
        Clean and normalize a data row from Excel/CSV import.
        
        Args:
            row_data: Dictionary containing row data
            
        Returns:
            dict: Cleaned and normalized row data
        """
        cleaned_row = {}
        
        for key, value in row_data.items():
            # Skip unnamed columns
            if not key or str(key).startswith('Unnamed'):
                continue
            
            # Normalize field name
            normalized_key = DataProcessingUtils.normalize_field_name(key)
            
            # Clean NaN values first
            value = DataProcessingUtils.clean_nan_values(value)
            
            # Handle special cases - name fields should always be treated as strings
            if normalized_key in ['first_name', 'middle_name', 'last_name']:
                cleaned_row[normalized_key] = DataProcessingUtils.parse_string_field(value)
                continue
            
            if normalized_key == "ssn" and value is None:
                cleaned_row[normalized_key] = ""
                continue
            
            # Handle address fields
            if normalized_key in ['address_1', 'address_2', 'city', 'address_state', 'county', 'country']:
                cleaned_row[normalized_key] = DataProcessingUtils.parse_string_field(value)
                continue
            elif normalized_key in ['zip_code', 'geo_code']:
                cleaned_row[normalized_key] = DataProcessingUtils.parse_integer_field(value)
                continue
            
            # Handle special complex field that contains both date and boolean
            if normalized_key == 'garnishment_fees_suspended_till' and isinstance(value, str):
                # Parse the complex field "2024-02-02 No" -> extract date part
                parts = str(value).strip().split()
                if parts:
                    # First part should be the date
                    date_part = parts[0]
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_date_field(date_part)
                    
                    # If there are more parts, handle support_second_family
                    if len(parts) > 1:
                        support_part = parts[1].lower()
                        if support_part in ['yes', 'true', '1']:
                            cleaned_row['support_second_family'] = True
                        elif support_part in ['no', 'false', '0']:
                            cleaned_row['support_second_family'] = False
                else:
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_date_field(value)
            # Apply appropriate parsing based on field name
            elif any(date_field in normalized_key.lower() for date_field in ['date', 'till', 'until']):
                cleaned_row[normalized_key] = DataProcessingUtils.parse_date_field(value)
            elif any(int_field in normalized_key.lower() for int_field in ['number', 'count', 'amount', 'id']):
                # Protect identifiers that must remain strings
                if normalized_key in ['ee_id', 'client_id', 'case_id', 'payee_id', 'ssn']:
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_string_field(value)
                else:
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_integer_field(value)
            elif any(bool_field in normalized_key.lower() for bool_field in ['status', 'support', 'active', 'is_']):
                # Check if it's a string field that shouldn't be converted to boolean
                if normalized_key in ['issuing_state', 'garnishment_type', 'home_state', 'work_state']:
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_string_field(value)
                else:
                    cleaned_row[normalized_key] = DataProcessingUtils.parse_boolean_field(value)
            else:
                # Keep original value for other fields (already cleaned of NaN)
                cleaned_row[normalized_key] = value
        
        return cleaned_row

    @staticmethod
    def validate_and_clean_employee_data(employee_data: dict) -> dict:
        """
        Validate and clean employee data with specific field handling.
        
        Args:
            employee_data: Dictionary containing employee data
            
        Returns:
            dict: Cleaned employee data
        """
        cleaned_data = employee_data.copy()
        
        # Date fields
        date_fields = ['garnishment_fees_suspended_till', 'issued_date', 'received_date', 
                      'start_date', 'stop_date', 'override_start_date', 'override_stop_date', 
                      'paid_till_date']
        
        # Integer fields
        integer_fields = ['number_of_exemptions', 'number_of_student_default_loan', 
                         'number_of_dependent_child', 'number_of_active_garnishment']
        
        # Boolean fields
        boolean_fields = ['support_second_family', 'garnishment_fees_status', 'is_active',
                         'is_consumer_debt', 'is_blind', 'is_spouse_blind']

        # String fields (explicitly validated to avoid coercion to integers)
        string_fields = [
            'ee_id', 'client_id','payee_id', 'first_name', 'middle_name', 'last_name',
            'marital_status', 'gender', 'home_state', 'work_state', 'ssn',
        ]
        
        # Process date fields
        for field in date_fields:
            if field in cleaned_data:
                cleaned_data[field] = DataProcessingUtils.parse_date_field(cleaned_data[field])
        
        # Process integer fields
        for field in integer_fields:
            if field in cleaned_data:
                cleaned_data[field] = DataProcessingUtils.parse_integer_field(cleaned_data[field])
        
        # Process boolean fields
        for field in boolean_fields:
            if field in cleaned_data:
                cleaned_data[field] = DataProcessingUtils.parse_boolean_field(cleaned_data[field])

        # Process string fields
        for field in string_fields:
            if field in cleaned_data:
                cleaned_data[field] = DataProcessingUtils.parse_string_field(cleaned_data[field])
        
        return cleaned_data

    @staticmethod
    def validate_client_exists(client_id: str) -> bool:
        """
        Validate if a client exists in the database.
        
        Args:
            client_id: Client ID to validate
            
        Returns:
            bool: True if client exists, False otherwise
        """
        try:
            from user_app.models import Client
            return Client.objects.filter(client_id=client_id).exists()
        except Exception:
            return False

    @staticmethod
    def get_default_filing_status() -> str:
        """
        Get default filing status if none is provided.
        
        Returns:
            str: Default filing status name
        """
        try:
            from processor.models import FedFilingStatus
            # Try to get a default filing status, fallback to 'single'
            default_status = FedFilingStatus.objects.filter(name__iexact='single').first()
            if default_status:
                return default_status.name
            
            # If 'single' doesn't exist, get the first available one
            first_status = FedFilingStatus.objects.first()
            if first_status:
                return first_status.name
                
            return 'single'  # Fallback
        except Exception:
            return 'single'

    @staticmethod
    def get_default_marital_status() -> str:
        """
        Get default marital status if none is provided.
        
        Returns:
            str: Default marital status
        """
        return 'single'  # Default marital status

    @staticmethod
    def is_field_empty(value: Any) -> bool:
        """
        Check if a field value should be considered empty.
        
        Args:
            value: Field value to check
            
        Returns:
            bool: True if field should be considered empty
        """
        if value is None:
            return True
        
        # Clean NaN values first
        cleaned_value = DataProcessingUtils.clean_nan_values(value)
        if cleaned_value is None:
            return True
        
        # Check for empty string
        if isinstance(cleaned_value, str) and cleaned_value.strip() == '':
            return True
        
        # Check for string representations of empty
        if isinstance(cleaned_value, str) and cleaned_value.strip().lower() in ['', 'nan', 'null', 'none', 'n/a', 'na']:
            return True
        
        return False

    @staticmethod
    def validate_and_fix_employee_data(employee_data: dict, auto_create_client: bool = False) -> tuple[dict, list]:
        """
        Validate and fix employee data, returning cleaned data and validation errors.
        
        Args:
            employee_data: Dictionary containing employee data
            auto_create_client: Whether to automatically create missing clients
            
        Returns:
            tuple: (cleaned_data, validation_errors)
        """
        cleaned_data = employee_data.copy()
        validation_errors = []
        
        # Clean the data first
        cleaned_data = DataProcessingUtils.validate_and_clean_employee_data(cleaned_data)
        
        # Validate and fix client_id
        client_id = cleaned_data.get('client_id')
        if DataProcessingUtils.is_field_empty(client_id):
            validation_errors.append("client_id is required")
        elif not DataProcessingUtils.validate_client_exists(client_id):
            if auto_create_client:
                # Try to create the missing client
                client_created = DataProcessingUtils.create_missing_client(client_id)
                if client_created:
                    validation_errors.append(f"Client '{client_id}' was not found and was created automatically.")
                else:
                    validation_errors.append(f"Client '{client_id}' not found and could not be created automatically.")
            else:
                validation_errors.append(f"Client '{client_id}' not found. Please create the client first.")
        
        # Validate and fix filing_status
        filing_status = cleaned_data.get('filing_status')
        if DataProcessingUtils.is_field_empty(filing_status):
            default_filing_status = DataProcessingUtils.get_default_filing_status()
            cleaned_data['filing_status'] = default_filing_status
            validation_errors.append(f"filing_status was empty, using default: '{default_filing_status}'")
        
        # Validate and fix marital_status
        marital_status = cleaned_data.get('marital_status')
        if DataProcessingUtils.is_field_empty(marital_status):
            default_marital_status = DataProcessingUtils.get_default_marital_status()
            cleaned_data['marital_status'] = default_marital_status
            validation_errors.append(f"marital_status was empty, using default: '{default_marital_status}'")
        
        # Validate required fields
        required_fields = ['ee_id', 'first_name', 'ssn', 'home_state', 'work_state']
        for field in required_fields:
            if DataProcessingUtils.is_field_empty(cleaned_data.get(field)):
                validation_errors.append(f"{field} is required")
        
        return cleaned_data, validation_errors

    @staticmethod
    def create_missing_client(client_id: str, default_data: dict = None) -> bool:
        """
        Create a missing client with default data.
        
        Args:
            client_id: Client ID to create
            default_data: Optional default data for the client
            
        Returns:
            bool: True if created successfully, False otherwise
        """
        try:
            from user_app.models import Client, PEO
            from processor.models import State
            
            if default_data is None:
                default_data = {}
            
            # Get default PEO (first available)
            default_peo = PEO.objects.first()
            if not default_peo:
                return False
            
            # Get default state (first available)
            default_state = State.objects.first()
            if not default_state:
                return False
            
            # Create client with default values
            client_data = {
                'client_id': client_id,
                'peo': default_peo,
                'state': default_state,
                'legal_name': default_data.get('legal_name', f'Client {client_id}'),
                'dba': default_data.get('dba', ''),
                'service_type': default_data.get('service_type', ''),
                'is_active': True
            }
            
            Client.objects.create(**client_data)
            return True
            
        except Exception as e:
            print(f"Error creating client {client_id}: {str(e)}")
            return False

    @staticmethod
    def debug_field_values(employee_data: dict, field_names: list = None) -> dict:
        """
        Debug function to see what values are being read from Excel/CSV.
        
        Args:
            employee_data: Dictionary containing employee data
            field_names: List of field names to debug (default: common fields)
            
        Returns:
            dict: Debug information about field values
        """
        if field_names is None:
            field_names = ['filing_status', 'marital_status', 'client_id', 'ee_id', 'first_name']
        
        debug_info = {
            'available_fields': list(employee_data.keys()),
            'field_values': {}
        }
        
        for field in field_names:
            value = employee_data.get(field)
            debug_info['field_values'][field] = {
                'raw_value': value,
                'type': type(value).__name__,
                'is_none': value is None,
                'is_pandas_nan': pd.isna(value) if value is not None else False,
                'is_empty_string': isinstance(value, str) and value.strip() == '',
                'cleaned_value': DataProcessingUtils.clean_nan_values(value),
                'is_field_empty': DataProcessingUtils.is_field_empty(value)
            }
        
        return debug_info
