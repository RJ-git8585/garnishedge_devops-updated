import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""
    pass


class MissingFieldError(ValidationError):
    """Raised when required fields are missing."""
    pass


class InvalidFormatError(ValidationError):
    """Raised when data format is invalid."""
    pass


class InvalidValueError(ValidationError):
    """Raised when field values are invalid."""
    pass


class FieldType(Enum):
    """Enumeration of field types for validation."""
    STRING = "string"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    EMAIL = "email"
    PHONE = "phone"


@dataclass
class ValidationRule:
    """Represents a validation rule for a field."""
    field_name: str
    field_type: FieldType
    required: bool = True
    min_value: Optional[Union[int, Decimal]] = None
    max_value: Optional[Union[int, Decimal]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[Any]] = None
    default_value: Optional[Any] = None
    custom_validator: Optional[callable] = None


class BaseValidator(ABC):
    """Abstract base class for input validators."""
    
    def __init__(self):
        self.validation_rules: List[ValidationRule] = []
        self.errors: List[str] = []
        
    @abstractmethod
    def get_validation_rules(self) -> List[ValidationRule]:
        """Define validation rules for the specific validator."""
        pass
    
    def validate(self, data: Union[str, dict]) -> Dict[str, Any]:
        """
        Validate input data according to defined rules.
        
        Args:
            data: Input data as JSON string or dictionary
            
        Returns:
            Dictionary containing validated and converted data
            
        Raises:
            ValidationError: If validation fails
        """
        self.errors.clear()
        
        # Parse JSON if string
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise InvalidFormatError(f"Invalid JSON format: {e}")
        
        if not isinstance(data, dict):
            raise InvalidFormatError("Input must be a dictionary or JSON string")
        
        # Get validation rules
        self.validation_rules = self.get_validation_rules()
        
        # Validate each rule
        validated_data = {}
        for rule in self.validation_rules:
            try:
                validated_value = self._validate_field(data, rule)
                validated_data[rule.field_name] = validated_value
            except ValidationError as e:
                self.errors.append(str(e))
        
        # Check for validation errors
        if self.errors:
            error_message = "Validation failed:\n" + "\n".join(f"- {error}" for error in self.errors)
            raise ValidationError(error_message)
        
        # Add any additional fields not in rules (if needed)
        for key, value in data.items():
            if key not in validated_data:
                validated_data[key] = value
                
        return validated_data
    
    def _validate_field(self, data: dict, rule: ValidationRule) -> Any:
        """Validate a single field according to its rule."""
        field_value = data.get(rule.field_name)
        
        # Handle missing fields
        if field_value is None:
            if rule.required:
                raise MissingFieldError(f"Required field '{rule.field_name}' is missing")
            elif rule.default_value is not None:
                field_value = rule.default_value
            else:
                return None
        
        # Convert and validate based on field type
        converted_value = self._convert_field_type(field_value, rule)
        
        # Apply validation rules
        self._apply_validation_rules(converted_value, rule)
        
        # Apply custom validator if provided
        if rule.custom_validator:
            try:
                rule.custom_validator(converted_value)
            except Exception as e:
                raise InvalidValueError(f"Custom validation failed for '{rule.field_name}': {e}")
        
        return converted_value
    
    def _convert_field_type(self, value: Any, rule: ValidationRule) -> Any:
        """Convert field value to the expected type."""
        try:
            if rule.field_type == FieldType.STRING:
                return str(value).strip()
            
            elif rule.field_type == FieldType.DECIMAL:
                if isinstance(value, Decimal):
                    return value
                return Decimal(str(value))
            
            elif rule.field_type == FieldType.INTEGER:
                return int(value)
            
            elif rule.field_type == FieldType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            
            elif rule.field_type == FieldType.LIST:
                if isinstance(value, list):
                    return value
                raise InvalidFormatError(f"Field '{rule.field_name}' must be a list")
            
            elif rule.field_type == FieldType.DICT:
                if isinstance(value, dict):
                    return value
                raise InvalidFormatError(f"Field '{rule.field_name}' must be a dictionary")
            
            elif rule.field_type == FieldType.EMAIL:
                email = str(value).strip().lower()
                if '@' not in email or '.' not in email:
                    raise InvalidFormatError(f"Invalid email format for '{rule.field_name}'")
                return email
            
            elif rule.field_type == FieldType.PHONE:
                phone = str(value).strip()
                # Basic phone validation - you can enhance this
                digits_only = ''.join(filter(str.isdigit, phone))
                if len(digits_only) < 10:
                    raise InvalidFormatError(f"Invalid phone number format for '{rule.field_name}'")
                return phone
            
            else:
                return value
                
        except (ValueError, InvalidOperation) as e:
            raise InvalidFormatError(f"Cannot convert '{rule.field_name}' to {rule.field_type.value}: {e}")
    
    def _apply_validation_rules(self, value: Any, rule: ValidationRule) -> None:
        """Apply validation rules to the converted value."""
        if value is None:
            return
        
        # Check allowed values
        if rule.allowed_values and value not in rule.allowed_values:
            raise InvalidValueError(
                f"Field '{rule.field_name}' must be one of {rule.allowed_values}, got '{value}'"
            )
        
        # Check numeric ranges
        if rule.field_type in [FieldType.DECIMAL, FieldType.INTEGER]:
            if rule.min_value is not None and value < rule.min_value:
                raise InvalidValueError(
                    f"Field '{rule.field_name}' must be >= {rule.min_value}, got {value}"
                )
            if rule.max_value is not None and value > rule.max_value:
                raise InvalidValueError(
                    f"Field '{rule.field_name}' must be <= {rule.max_value}, got {value}"
                )
        
        # Check string length
        if rule.field_type == FieldType.STRING:
            if rule.min_length is not None and len(str(value)) < rule.min_length:
                raise InvalidValueError(
                    f"Field '{rule.field_name}' must be at least {rule.min_length} characters"
                )
            if rule.max_length is not None and len(str(value)) > rule.max_length:
                raise InvalidValueError(
                    f"Field '{rule.field_name}' must be at most {rule.max_length} characters"
                )


class WithholdingInputValidator(BaseValidator):
    """Validator for withholding calculation input data."""
    
    def get_validation_rules(self) -> List[ValidationRule]:
        """Define validation rules for withholding calculations."""
        return [
            # Required employee information (matching actual input data)
            ValidationRule("ee_id", FieldType.STRING, required=True, min_length=1, max_length=50),
            ValidationRule("work_state", FieldType.STRING, required=True, min_length=2, max_length=50),
            ValidationRule("home_state", FieldType.STRING, required=False, min_length=2, max_length=50),
            ValidationRule("issuing_state", FieldType.STRING, required=False, min_length=2, max_length=50),
            
            # Boolean flags (matching actual input data)
            ValidationRule("support_second_family", FieldType.BOOLEAN, required=True),
            ValidationRule("arrears_greater_than_12_weeks", FieldType.BOOLEAN, required=True),
            
            # Financial amounts - all should be non-negative (matching actual input data)
            ValidationRule("gross_pay", FieldType.DECIMAL, required=True, min_value=Decimal("0")),
            ValidationRule("wages", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("commission_and_bonus", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("non_accountable_allowances", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # Tax amounts (matching actual input data)
            ValidationRule("payroll_taxes", FieldType.DICT, required=False, default_value={}),
            
            # Support amounts (matching actual input data and new enum values)
            ValidationRule("current_child_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("past_due_child_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("current_medical_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("past_due_medical_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("current_spousal_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("past_due_spousal_support", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("insurance_premiums", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("court_fee", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # New deduction type fields
            ValidationRule("child_support_arrears", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("medical_support_arrears", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("spousal_support_arrears", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("fees", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("child_support_arrear", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("medical_support_arrear", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("spousal_support_arrear", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("house_payment", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("insurance_payment", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("remaining_child_support_arrears", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("remaining_spousal_support_arrears", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # Additional fields from input data
            ValidationRule("batch_id", FieldType.STRING, required=False),
            ValidationRule("no_of_exemption_including_self", FieldType.INTEGER, required=False, min_value=0, default_value=0),
            ValidationRule("is_multiple_garnishment_type", FieldType.BOOLEAN, required=False, default_value=False),
            ValidationRule("no_of_student_default_loan", FieldType.INTEGER, required=False, min_value=0, default_value=0),
            ValidationRule("pay_period", FieldType.STRING, required=False),
            ValidationRule("filing_status", FieldType.STRING, required=False),
            ValidationRule("net_pay", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("statement_of_exemption_received_date", FieldType.STRING, required=False),
            ValidationRule("garn_start_date", FieldType.STRING, required=False),
            ValidationRule("non_consumer_debt", FieldType.BOOLEAN, required=False, default_value=False),
            ValidationRule("consumer_debt", FieldType.BOOLEAN, required=False, default_value=False),
            ValidationRule("age", FieldType.INTEGER, required=False, min_value=0),
            ValidationRule("spouse_age", FieldType.INTEGER, required=False, min_value=0),
            ValidationRule("is_spouse_blind", FieldType.BOOLEAN, required=False, default_value=False),
            ValidationRule("no_of_dependent_child", FieldType.INTEGER, required=False, min_value=0, default_value=0),
            ValidationRule("ftb_type", FieldType.STRING, required=False),
            
            # Complex fields
            ValidationRule("garnishment_data", FieldType.LIST, required=False, default_value=[]),
            ValidationRule("garnishment_orders", FieldType.LIST, required=False, default_value=[]),
        ]
    
    def validate_state_code(self, state: str) -> None:
        """Custom validator for state codes."""
        # List of valid US state codes - you can expand this
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        }
        
        state_upper = state.upper()
        if len(state_upper) == 2 and state_upper in valid_states:
            return
        
        # Allow full state names as well
        if len(state) > 2:
            return  # Assume full state name is valid
        
        raise InvalidValueError(f"Invalid state code: {state}")


class EmployeeInputValidator(BaseValidator):
    """Validator for basic employee information."""
    
    def get_validation_rules(self) -> List[ValidationRule]:
        """Define validation rules for employee data."""
        return [
            ValidationRule("employee_id", FieldType.STRING, required=True, min_length=1, max_length=50),
            ValidationRule("first_name", FieldType.STRING, required=True, min_length=1, max_length=50),
            ValidationRule("last_name", FieldType.STRING, required=True, min_length=1, max_length=50),
            ValidationRule("email", FieldType.EMAIL, required=False),
            ValidationRule("phone", FieldType.PHONE, required=False),
            ValidationRule("department", FieldType.STRING, required=False, max_length=100),
            ValidationRule("hire_date", FieldType.STRING, required=False),  # ISO date format
            ValidationRule("status", FieldType.STRING, required=False, 
                         allowed_values=["active", "inactive", "terminated"], default_value="active"),
        ]


class PayrollInputValidator(BaseValidator):
    """Validator for payroll calculation input data."""
    
    def get_validation_rules(self) -> List[ValidationRule]:
        """Define validation rules for payroll calculations."""
        return [
            # Client and Employee identification
            ValidationRule("client_id", FieldType.STRING, required=True, min_length=1, max_length=50),
            ValidationRule("ee_id", FieldType.STRING, required=True, min_length=1, max_length=50),
            
            # Pay period information
            ValidationRule("pay_period", FieldType.STRING, required=True, 
                         allowed_values=["Weekly", "Bi-weekly", "Semi-monthly", "Monthly", "Daily"], 
                         min_length=1, max_length=20),
            ValidationRule("payroll_date", FieldType.STRING, required=True),  
            ValidationRule("pay_period_start", FieldType.STRING, required=False), 
            ValidationRule("pay_period_end", FieldType.STRING, required=False),   
            
            # Earnings
            ValidationRule("wages", FieldType.DECIMAL, required=True, min_value=Decimal("0")),
            ValidationRule("commission_and_bonus", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("non_accountable_allowances", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("gross_pay", FieldType.DECIMAL, required=True, min_value=Decimal("0")),
            ValidationRule("net_pay", FieldType.DECIMAL, required=True, min_value=Decimal("0")),
            
            # Legacy earnings fields for backward compatibility
            ValidationRule("commission", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("bonus", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # Payroll taxes (as dictionary)
            ValidationRule("payroll_taxes", FieldType.DICT, required=False, default_value={}),
            
            # Individual tax components (for backward compatibility)
            ValidationRule("federal_income_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("state_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("local_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("medicare_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("social_security_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("wilmington_tax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("california_sdi", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # Pre-tax deductions
            ValidationRule("medical_insurance_pretax", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("life_insurance", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("retirement_401k", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("industrial_insurance", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("union_dues", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            
            # Legacy deduction fields for backward compatibility
            ValidationRule("health_insurance", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("dental_insurance", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
            ValidationRule("other_deductions", FieldType.DECIMAL, required=False, min_value=Decimal("0"), default_value=Decimal("0")),
        ]


# Factory function for easy validator creation
def create_validator(validator_type: str) -> BaseValidator:
    """
    Factory function to create validators.
    
    Args:
        validator_type: Type of validator ('withholding', 'employee', 'payroll')
        
    Returns:
        Appropriate validator instance
    """
    validators = {
        'withholding': WithholdingInputValidator,
        'employee': EmployeeInputValidator,
        'payroll': PayrollInputValidator,
    }
    
    if validator_type not in validators:
        raise ValueError(f"Unknown validator type: {validator_type}. Available types: {list(validators.keys())}")
    
    return validators[validator_type]()
