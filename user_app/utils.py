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
            
            # Handle numeric values
            if isinstance(bool_value, (int, float)):
                return bool(bool_value)
            
            return None
            
        except Exception:
            return None

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
            
            # Clean NaN values first
            value = DataProcessingUtils.clean_nan_values(value)
            
            # Handle special cases
            if key == "social_security_number" and value is None:
                cleaned_row[key] = ""
                continue
            
            # Apply appropriate parsing based on field name
            if any(date_field in key.lower() for date_field in ['date', 'till', 'until']):
                cleaned_row[key] = DataProcessingUtils.parse_date_field(value)
            elif any(int_field in key.lower() for int_field in ['number', 'count', 'amount', 'id']):
                cleaned_row[key] = DataProcessingUtils.parse_integer_field(value)
            elif any(bool_field in key.lower() for bool_field in ['status', 'support', 'active', 'is_']):
                cleaned_row[key] = DataProcessingUtils.parse_boolean_field(value)
            else:
                # Keep original value for other fields (already cleaned of NaN)
                cleaned_row[key] = value
        
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
        if client_id:
            if not DataProcessingUtils.validate_client_exists(client_id):
                if auto_create_client:
                    # Try to create the missing client
                    client_created = DataProcessingUtils.create_missing_client(client_id)
                    if client_created:
                        validation_errors.append(f"Client '{client_id}' was not found and was created automatically.")
                    else:
                        validation_errors.append(f"Client '{client_id}' not found and could not be created automatically.")
                else:
                    validation_errors.append(f"Client '{client_id}' not found. Please create the client first.")
        else:
            validation_errors.append("client_id is required")
        
        # Validate and fix filing_status
        filing_status = cleaned_data.get('filing_status')
        if not filing_status:
            default_filing_status = DataProcessingUtils.get_default_filing_status()
            cleaned_data['filing_status'] = default_filing_status
            validation_errors.append(f"filing_status was empty, using default: '{default_filing_status}'")
        
        # Validate and fix marital_status
        marital_status = cleaned_data.get('marital_status')
        if not marital_status:
            default_marital_status = DataProcessingUtils.get_default_marital_status()
            cleaned_data['marital_status'] = default_marital_status
            validation_errors.append(f"marital_status was empty, using default: '{default_marital_status}'")
        
        # Validate required fields
        required_fields = ['ee_id', 'first_name', 'ssn', 'home_state', 'work_state']
        for field in required_fields:
            if not cleaned_data.get(field):
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
