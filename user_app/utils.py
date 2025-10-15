import hashlib
import re
import pandas as pd
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
    def parse_date_field(date_value: Any) -> Optional[str]:
        """
        Parse various date formats and return YYYY-MM-DD format string.
        
        Args:
            date_value: Date value in any supported format
            
        Returns:
            str: Date in YYYY-MM-DD format or None if invalid
        """
        if date_value is None or date_value == '' or str(date_value).strip() == '':
            return None
        
        # Handle pandas NaN values
        if pd.isna(date_value):
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
        if int_value is None or str(int_value).strip() == '':
            return None
        
        # Handle pandas NaN values
        if pd.isna(int_value):
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
        if bool_value is None or str(bool_value).strip() == '':
            return None
        
        # Handle pandas NaN values
        if pd.isna(bool_value):
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
            
            # Handle special cases
            if key == "social_security_number" and isinstance(value, float) and pd.isna(value):
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
                # Keep original value for other fields
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
