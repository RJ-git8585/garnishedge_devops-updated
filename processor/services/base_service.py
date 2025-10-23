"""
Base service class with common functionality for garnishment calculations.
Contains shared utilities and validation methods.
"""

import logging
from typing import Dict, Set, List, Any
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    GarnishmentDataKeys as GDK
)

logger = logging.getLogger(__name__)


class BaseService:
    """
    Base service class containing common functionality for garnishment calculations.
    """

    def __init__(self):
        self.logger = logger

    def validate_fields(self, record: Dict, required_fields: List[str]) -> List[str]:
        """
        Validates required fields and returns a list of missing fields.
        Uses set operations for efficiency if required_fields is large.
        """
        if len(required_fields) > 10:
            return list(set(required_fields) - set(record))
        return [field for field in required_fields if field not in record]

    def get_all_garnishment_types(self, cases_data: List[Dict]) -> Set[str]:
        """
        Extract all unique garnishment types from the cases data.
        Handles both single and multi-garnishment cases.
        """
        garnishment_types = set()
        
        self.logger.debug(f"Processing {len(cases_data)} cases for garnishment types")
        
        for i, case in enumerate(cases_data):
            self.logger.debug(f"Case {i} keys: {list(case.keys())}")
            garnishment_data = case.get(EE.GARNISHMENT_DATA, [])
            self.logger.debug(f"Case {i} garnishment_data: {garnishment_data}")
            
            for j, garnishment in enumerate(garnishment_data):
                self.logger.debug(f"Garnishment {j}: {garnishment}")
                garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get(GDK.TYPE)
                self.logger.debug(f"Extracted garnishment_type: {garnishment_type}")
                if garnishment_type:
                    normalized_type = garnishment_type.lower().strip()
                    garnishment_types.add(normalized_type)
                    self.logger.debug(f"Added normalized type: {normalized_type}")
                    
        self.logger.debug(f"Final garnishment_types: {garnishment_types}")
        return garnishment_types

    def is_multi_garnishment_case(self, case_data: Dict) -> bool:
        """
        Determine if a case contains multiple garnishment types.
        Returns True if more than one garnishment type is present.
        """
        garnishment_data = case_data.get(EE.GARNISHMENT_DATA, [])
        return len(garnishment_data) > 1

    def get_case_garnishment_types(self, case_data: Dict) -> Set[str]:
        """
        Extract garnishment types for a specific case.
        Used for multi-garnishment case processing.
        """
        garnishment_types = set()
        garnishment_data = case_data.get(EE.GARNISHMENT_DATA, [])
        
        for garnishment in garnishment_data:
            garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get(GDK.TYPE)
            if garnishment_type:
                normalized_type = garnishment_type.lower().strip()
                garnishment_types.add(normalized_type)
                
        return garnishment_types

    def filter_config_for_case(self, full_config_data: Dict, case_garnishment_types: Set[str]) -> Dict:
        """
        Filter configuration data to include only relevant types for a specific case.
        This is particularly useful for multi-garnishment cases.
        """
        filtered_config = {}
        
        for garnishment_type in case_garnishment_types:
            if garnishment_type in full_config_data:
                filtered_config[garnishment_type] = full_config_data[garnishment_type]
                    
        return filtered_config

    def _extract_case_id_from_garnishment_data(self, record: Dict, garnishment_type: str) -> str:
        """
        Extract case_id from garnishment_data for a specific garnishment type.
        Returns the first case_id found for the garnishment type, or the garnishment_type as fallback.
        """
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
            
            for garnishment in garnishment_data:
                if garnishment.get('type', '').lower() == garnishment_type.lower():
                    data_list = garnishment.get('data', [])
                    if data_list and len(data_list) > 0:
                        return data_list[0].get('case_id', garnishment_type)
            
            # Fallback to garnishment_type if no case_id found
            return garnishment_type
            
        except Exception as e:
            self.logger.warning(f"Error extracting case_id for {garnishment_type}: {e}")
            return garnishment_type

    def get_garnishment_rules_mapping(self) -> Dict:
        """
        Get the mapping of garnishment types to their required fields and calculation methods.
        """
        return {
            GT.CHILD_SUPPORT: {
                "fields": [
                    EE.ARREARS_GREATER_THAN_12_WEEKS, EE.SUPPORT_SECOND_FAMILY,
                    CA.GROSS_PAY, PT.PAYROLL_TAXES
                ],
                "calculate": "calculate_child_support"
            },
            GT.FEDERAL_TAX_LEVY: {
                "fields": [EE.FILING_STATUS, EE.PAY_PERIOD, CA.NET_PAY, EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE],
                "calculate": "calculate_federal_tax"
            },
            GT.STUDENT_DEFAULT_LOAN: {
                "fields": [CA.GROSS_PAY, EE.PAY_PERIOD, EE.NO_OF_STUDENT_DEFAULT_LOAN, PT.PAYROLL_TAXES],
                "calculate": "calculate_student_loan"
            },
            GT.STATE_TAX_LEVY: {
                "fields": [EE.GROSS_PAY, EE.WORK_STATE],
                "calculate": "calculate_state_tax_levy"
            },
            GT.CREDITOR_DEBT: {
                "fields": [EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD],
                "calculate": "calculate_creditor_debt"
            },
            GT.SPOUSAL_AND_MEDICAL_SUPPORT: {
                "fields": [
                    EE.ARREARS_GREATER_THAN_12_WEEKS, EE.SUPPORT_SECOND_FAMILY,
                    CA.GROSS_PAY, PT.PAYROLL_TAXES
                ],
                "calculate": "calculate_spousal_and_medical_support"
            },
            GT.BANKRUPTCY: {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, GT.SPOUSAL_SUPPORT_AMOUNT, GT.BANKRUPTCY_AMOUNT
                ],
                "calculate": "calculate_bankruptcy"
            },
            "ftb_ewot": {
                "fields": [EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS],
                "calculate": "calculate_ftb"
            },
            "ftb_court": {  
                "fields": [EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS],
                "calculate": "calculate_ftb"
            },
            "ftb_vehicle": {  
                "fields": [EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS],
                "calculate": "calculate_ftb"
            },
        }

    def validate_garnishment_type(self, garnishment_type: str) -> bool:
        """
        Validate if a garnishment type is supported.
        """
        rules_mapping = self.get_garnishment_rules_mapping()
        return garnishment_type.lower() in rules_mapping

    def get_required_fields_for_type(self, garnishment_type: str) -> List[str]:
        """
        Get required fields for a specific garnishment type.
        """
        rules_mapping = self.get_garnishment_rules_mapping()
        rule = rules_mapping.get(garnishment_type.lower())
        return rule.get("fields", []) if rule else []

    def get_calculation_method_for_type(self, garnishment_type: str) -> str:
        """
        Get the calculation method name for a specific garnishment type.
        """
        rules_mapping = self.get_garnishment_rules_mapping()
        rule = rules_mapping.get(garnishment_type.lower())
        return rule.get("calculate", "") if rule else ""

    def log_calculation_start(self, garnishment_type: str, employee_id: str) -> None:
        """
        Log the start of a calculation.
        """
        self.logger.info(f"Starting {garnishment_type} calculation for employee {employee_id}")

    def log_calculation_end(self, garnishment_type: str, employee_id: str, success: bool) -> None:
        """
        Log the end of a calculation.
        """
        status = "successful" if success else "failed"
        self.logger.info(f"{garnishment_type} calculation {status} for employee {employee_id}")

    def log_calculation_error(self, garnishment_type: str, employee_id: str, error: str) -> None:
        """
        Log calculation errors.
        """
        self.logger.error(f"Error in {garnishment_type} calculation for employee {employee_id}: {error}")

    def sanitize_record(self, record: Dict) -> Dict:
        """
        Sanitize and clean the input record.
        """
        sanitized = {}
        for key, value in record.items():
            if value is not None:
                if isinstance(value, str):
                    sanitized[key] = value.strip()
                else:
                    sanitized[key] = value
        return sanitized

    def extract_employee_info(self, record: Dict) -> Dict:
        """
        Extract basic employee information from the record.
        """
        return {
            'employee_id': record.get(EE.EMPLOYEE_ID),
            'work_state': record.get(EE.WORK_STATE),
            'pay_period': record.get(EE.PAY_PERIOD),
            'filing_status': record.get(EE.FILING_STATUS),
            'gross_pay': record.get(CA.GROSS_PAY),
            'net_pay': record.get(CA.NET_PAY)
        }

    def extract_garnishment_info(self, record: Dict) -> List[Dict]:
        """
        Extract garnishment information from the record.
        """
        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
        extracted = []
        
        for garnishment in garnishment_data:
            extracted.append({
                'type': garnishment.get(GDK.TYPE, garnishment.get(EE.GARNISHMENT_TYPE, '')),
                'data': garnishment.get(GDK.DATA, [])
            })
        
        return extracted

    def validate_calculation_prerequisites(self, record: Dict, garnishment_type: str) -> Dict:
        """
        Validate prerequisites for a calculation.
        Returns a dictionary with validation results.
        """
        validation_result = {
            'is_valid': True,
            'missing_fields': [],
            'errors': []
        }
        
        # Check if garnishment type is supported
        if not self.validate_garnishment_type(garnishment_type):
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Unsupported garnishment type: {garnishment_type}")
            return validation_result
        
        # Check required fields
        required_fields = self.get_required_fields_for_type(garnishment_type)
        missing_fields = self.validate_fields(record, required_fields)
        
        if missing_fields:
            validation_result['is_valid'] = False
            validation_result['missing_fields'] = missing_fields
            validation_result['errors'].append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Check garnishment data
        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
        if not garnishment_data:
            validation_result['is_valid'] = False
            validation_result['errors'].append("No garnishment data provided")
        
        return validation_result
