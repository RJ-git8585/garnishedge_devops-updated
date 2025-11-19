"""
Refactored calculation service using modular architecture.
This service orchestrates the various specialized services for garnishment calculations.
"""

import logging
import re
from typing import Dict, Set, List, Any
from processor.services.config_loader import ConfigLoader
from processor.services.fee_calculator import FeeCalculator
from user_app.models.payee.payee import PayeeDetails
from processor.services.garnishment_calculator import GarnishmentCalculator
from processor.services.database_manager import DatabaseManager
from processor.services.base_service import BaseService
from processor.garnishment_library.calculations import StateAbbreviations
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    CommonConstants,
    GarnishmentResultFields as GRF,
    ErrorMessages as EM
)

logger = logging.getLogger(__name__)


class CalculationDataView:
    """
    Main service class to handle all garnishment calculations and database operations.
    Now uses a modular architecture with specialized services.
    """

    def __init__(self):
        self.logger = logger
        # Initialize specialized services
        self.config_loader = ConfigLoader()
        self.fee_calculator = FeeCalculator()
        self.database_manager = DatabaseManager()
        self.base_service = BaseService()
        
        # Initialize garnishment calculator with dependencies
        self.garnishment_calculator = GarnishmentCalculator(
            self.fee_calculator
        )

    def preload_config_data(self, garnishment_types: Set[str]) -> Dict[str, Any]:
        """
        Preloads configuration data for the requested garnishment types.
        Delegates to ConfigLoader service.
        """
        return self.config_loader.preload_config_data(garnishment_types)

    def preload_garnishment_fees(self) -> list:
        """
        Preloads garnishment fee configurations from the DB once.
        Delegates to ConfigLoader service.
        """
        return self.config_loader.preload_garnishment_fees()

    def validate_fields(self, record: Dict, required_fields: List[str]) -> List[str]:
        """
        Validates required fields and returns a list of missing fields.
        Delegates to BaseService.
        """
        return self.base_service.validate_fields(record, required_fields)

    def resolve_payee_type(self, case_id: str, garnishment_type: str) -> dict:
        try:
            payee = PayeeDetails.objects.get(case_id__iexact=case_id)

            name = (payee.name or "").strip()
            normalized_upper = name.upper()
            normalized_lower = name.lower()

            # Exact matches
            if normalized_upper == "VEHICLE REGISTRATION":
                return {"payee_type": GT.FTB_VEHICLE}

            if normalized_upper == "CA FTB EFT":
                return {"payee_type": GT.FTB_EWOT}

            if normalized_upper == "COURT DEBT COLLECTIONS":
                return {"payee_type": GT.FTB_COURT}

            # Contains "creditors"
            if "creditors" in normalized_lower:
                return {"payee_type": GT.CREDITOR_DEBT}

            # Match STATE TAX variations: state tax, state_tax, state-tax, statetax, etc.
            if re.search(r"state[^a-zA-Z]*tax", normalized_lower):
                return {"payee_type": GT.STATE_TAX_LEVY}

            # Default fallback
            return {"payee_type": GT.STATE_TAX_LEVY_FTB_EWOT}

        except Exception as e:
            return {
                "error": f"Error resolving payee type for case '{case_id}': {str(e)}"
            }



    
    def calculate_garnishment(self, garnishment_type: str, record: Dict, 
                             config_data: Dict, garn_fees: float = None,code:str = None) -> Dict:
        """
        Handles garnishment calculations based on type.
        Uses the modular garnishment calculator.
        """
        garnishment_type_lower = garnishment_type.lower()
        garnishment_type_lower = (garnishment_type or "").lower()

        special_types = {
            GT.STATE_TAX_LEVY_FTB_EWOT,
            GT.CREDITOR_FTB_COURT_VEHICLE
        }

        # CASE 1: If garnishment type falls under special types OR matches specific codes
        if garnishment_type_lower in special_types or code in ("G506", "G507"):
            
            # Call the payee resolver safely
            resolved = self.resolve_payee_type(
                record.get(EE.CASE_ID),
                garnishment_type
            )

            # Handle resolver error
            if resolved.get("error"):
                return resolved

            # Overwrite the garnishment_type_lower with the resolved type
            garnishment_type = resolved.get("payee_type")
        else:
            garnishment_type = garnishment_type_lower

        # Validate prerequisites
        validation_result = self.base_service.validate_calculation_prerequisites(
            record, garnishment_type
        )
        
        if not validation_result['is_valid']:
            return {"error": f"Validation failed: {'; '.join(validation_result['errors'])}"}
        
        # Get calculation method
        calculation_method = self.base_service.get_calculation_method_for_type(garnishment_type)
        if not calculation_method:
            return {"error": f"Unsupported garnishment type: {garnishment_type}"}
        
        # Log calculation start
        self.base_service.log_calculation_start(garnishment_type_lower, record.get(EE.EMPLOYEE_ID))
        
        try:
            # Route to appropriate calculation method
            if calculation_method == "calculate_child_support":
                result = self.garnishment_calculator.calculate_child_support(record, config_data, garn_fees)
            elif calculation_method == "calculate_federal_tax":
                result = self.garnishment_calculator.calculate_federal_tax(record, config_data, garn_fees)
            elif calculation_method == "calculate_student_loan":
                result = self.garnishment_calculator.calculate_student_loan(record, config_data, garn_fees)
            elif calculation_method == "calculate_state_tax_levy":
                result = self.garnishment_calculator.calculate_state_tax_levy(record, config_data, garn_fees)
            elif calculation_method == "calculate_creditor_debt":
                result = self.garnishment_calculator.calculate_creditor_debt(record, config_data, garn_fees)
            elif calculation_method == "calculate_spousal_and_medical_support":
                result = self.garnishment_calculator.calculate_spousal_and_medical_support(record, config_data, garn_fees)
            elif calculation_method == "calculate_bankruptcy":
                result = self.garnishment_calculator.calculate_bankruptcy(record, config_data, garn_fees)
            elif calculation_method == "calculate_ftb":
                result = self.garnishment_calculator.calculate_ftb(record, config_data, garn_fees)
            else:
                return {"error": f"Unknown calculation method: {calculation_method}"}
            
            # Log calculation end
            success = not (isinstance(result, dict) and result.get(GRF.ERROR))
            self.base_service.log_calculation_end(garnishment_type, record.get(EE.EMPLOYEE_ID), success)
            
            return result
            
        except Exception as e:
            self.base_service.log_calculation_error(garnishment_type_lower, record.get(EE.EMPLOYEE_ID), str(e))
            return {"error": f"Error calculating {garnishment_type}: {e}"}

    def calculate_multiple_garnishment(self, record: Dict, config_data: Dict, 
                                      garn_fees: float = None) -> Dict:
        """
        Calculate multiple garnishment with standardized result structure.
        Delegates to GarnishmentCalculator.
        """
        return self.garnishment_calculator.calculate_multiple_garnishment(record, config_data, garn_fees)

    def calculate_garnishment_wrapper(self, record: Dict, config_data: Dict, 
                                     garn_fees: float = None) -> Any:
        """
        Wrapper function for parallel processing of garnishment calculations.
        """
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            if not garnishment_data:
                return None
                
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "").strip().lower()
            result = self.calculate_garnishment(garnishment_type, record, config_data, garn_fees)
            
            if result is None:
                return CommonConstants.NOT_FOUND
            elif result == CommonConstants.NOT_PERMITTED:
                return CommonConstants.NOT_PERMITTED
            else:
                return result
                
        except Exception as e:
            self.logger.error(f"{EM.ERROR_IN_GARNISHMENT_WRAPPER} {e}")
            return {"error": f"{EM.ERROR_IN_GARNISHMENT_WRAPPER} {e}"}

    def calculate_garnishment_result(self, case_info: Dict, batch_id: str, 
                                   config_data: Dict, garn_fees: float = None) -> Dict:
        """
        Calculates garnishment result for a single case.
        """
        try:
            state = StateAbbreviations(case_info.get(EE.WORK_STATE)).get_state_name_and_abbr()
            ee_id = case_info.get(EE.EMPLOYEE_ID)
            is_multiple_garnishment_type = case_info.get("is_multiple_garnishment_type")
            
            if is_multiple_garnishment_type:
                calculated_result = self.calculate_multiple_garnishment(case_info, config_data, garn_fees)
            else:
                calculated_result = self.calculate_garnishment_wrapper(case_info, config_data, garn_fees)
            
            if isinstance(calculated_result, dict) and GRF.ERROR in calculated_result:
                return {
                    GRF.ERROR: calculated_result[GRF.ERROR],
                    "status_code": calculated_result.get("status_code", 500),
                    GRF.EMPLOYEE_ID: ee_id,
                    GRF.WORK_STATE: state
                }
            
            if calculated_result == CommonConstants.NOT_FOUND:
                return {
                    GRF.ERROR: f"Garnishment could not be calculated for employee {ee_id} because the state of {state} has not been implemented yet."
                }
            elif calculated_result == CommonConstants.NOT_PERMITTED:
                return {GRF.ERROR: f"In {state}, garnishment for creditor debt is not permitted."}
            elif not calculated_result:
                return {
                    GRF.ERROR: f"{EM.COULD_NOT_CALCULATE_GARNISHMENT} {ee_id}"
                }
            
            return calculated_result
            
        except Exception as e:
            self.logger.error(f"{EM.UNEXPECTED_ERROR} {case_info.get(EE.EMPLOYEE_ID)}: {e}")
            return {
                GRF.ERROR: f"{EM.UNEXPECTED_ERROR} {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"
            }

    def process_and_store_case(self, case_info: Dict, batch_id: str, 
                              config_data: Dict, garn_fees: float = None) -> Dict:
        """
        Process and store garnishment case data in the database.
        Delegates to DatabaseManager.
        """
        try:
            # First calculate the garnishment result
            result = self.calculate_garnishment_result(case_info, batch_id, config_data, garn_fees)
            
            if isinstance(result, dict) and result.get(GRF.ERROR):
                return result
            
            # Store the case data
            store_result = self.database_manager.process_and_store_case(
                case_info, batch_id, config_data,result, garn_fees
            )
            
            if store_result.get("error"):
                return store_result
            
            # Update calculation results in database
            first_case_id = self.base_service._extract_case_id_from_garnishment_data(case_info, "")
            if first_case_id and isinstance(result, dict):
                self.database_manager.update_calculation_results(first_case_id, result, batch_id, case_info)
            
            # Clean up result for return
            if isinstance(result, dict):
                result.pop(CR.WITHHOLDING_BASIS, None)
                result.pop(CR.WITHHOLDING_CAP, None)
            
            return result
            
        except Exception as e:
            return {GRF.ERROR: f"{EM.ERROR_PROCESSING_CASE} {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"}

    def get_all_garnishment_types(self, cases_data: List[Dict]) -> Set[str]:
        """
        Extract all unique garnishment types from the cases data.
        Delegates to BaseService.
        """
        return self.base_service.get_all_garnishment_types(cases_data)

    def is_multi_garnishment_case(self, case_data: Dict) -> bool:
        """
        Determine if a case contains multiple garnishment types.
        Delegates to BaseService.
        """
        return self.base_service.is_multi_garnishment_case(case_data)

    def get_case_garnishment_types(self, case_data: Dict) -> Set[str]:
        """
        Extract garnishment types for a specific case.
        Delegates to BaseService.
        """
        return self.base_service.get_case_garnishment_types(case_data)

    def filter_config_for_case(self, full_config_data: Dict, case_garnishment_types: Set[str]) -> Dict:
        """
        Filter configuration data to include only relevant types for a specific case.
        Delegates to BaseService.
        """
        return self.base_service.filter_config_for_case(full_config_data, case_garnishment_types)

    # Legacy methods for backward compatibility
    def get_garnishment_fees(self, record: Dict, total_withhold_amt: float, 
                            garn_fees: float = None) -> str:
        """
        Calculates garnishment fees based on employee data and suspension status.
        Delegates to FeeCalculator.
        """
        return self.fee_calculator.get_garnishment_fees(record, total_withhold_amt, garn_fees)

    def get_rounded_garnishment_fee(self, work_state: str, garnishment_type: str, 
                                   pay_period: str, withholding_amt: float, 
                                   garn_fees: float = None) -> Any:
        """
        Applies garnishment fee rule and rounds the result if it is numeric.
        Delegates to FeeCalculator.
        """
        return self.fee_calculator.get_rounded_garnishment_fee(
            work_state, garnishment_type, pay_period, withholding_amt, garn_fees
        )

    def is_garnishment_fee_deducted(self, record: Dict) -> bool:
        """
        Determines if garnishment fees can be deducted for the employee.
        Delegates to FeeCalculator.
        """
        return self.fee_calculator.is_garnishment_fee_deducted(record)

    def _get_employee_details(self, employee_id: str) -> Dict:
        """
        Fetches employee details by ID.
        Delegates to FeeCalculator.
        """
        return self.fee_calculator._get_employee_details(employee_id)

    def _handle_insufficient_pay_garnishment(self, record: Dict, disposable_earning: float, 
                                           total_mandatory_deduction_obj: float) -> Dict:
        """
        Helper to set insufficient pay messages and common fields.
        Delegates to ResultFormatter.
        """
        return self.result_formatter._handle_insufficient_pay_garnishment(
            record, disposable_earning, total_mandatory_deduction_obj
        )

    def _create_standardized_result(self, garnishment_type: str, record: Dict, 
                                  calculation_result: Dict = None, error_message: str = None) -> Dict:
        """
        Creates a standardized result structure for garnishment calculations.
        Delegates to ResultFormatter.
        """
        return self.result_formatter.create_standardized_result(
            garnishment_type, record, calculation_result, error_message
        )
