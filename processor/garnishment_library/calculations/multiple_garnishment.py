import logging
import decimal
from typing import Any, Dict, List, Optional
from processor.garnishment_library.utils import StateAbbreviations,MultipleGarnishmentPriorityHelper,FinanceUtils
from processor.garnishment_library.utils.response import CalculationResponse as CR
from processor.garnishment_library.calculations.state_tax import StateTaxLevyCalculator
from processor.garnishment_library.calculations.ftb import FTB
from processor.garnishment_library.calculations.bankruptcy import Bankruptcy
from processor.garnishment_library.calculations.federal_case import FederalTax
from processor.garnishment_library.calculations.child_support import ChildSupport, ChildSupportHelper
from processor.garnishment_library.calculations.student_loan import StudentLoanCalculator
from processor.garnishment_library.calculations.creditor_debt import CreditorDebtCalculator
from processor.garnishment_library.calculations.deductions_priority import WithholdingProcessor
from user_app.constants import (
    EmployeeFields as EE,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    GarnishmentTypeFields as GT,

)
from user_app.constants import ConfigDataKeys as CDK
from processor.serializers import MultipleGarnPriorityOrderCRUDSerializer
from decimal import Decimal
import traceback as t 
from processor.models import MultipleGarnPriorityOrders



# Configure logging similar to deductions_priority.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Custom Exceptions  ---
class GarnishmentError(Exception):
    """Base exception for garnishment calculation errors."""
    pass

class PriorityOrderError(GarnishmentError):
    """Error related to fetching or processing priority orders."""
    pass

class CalculationError(GarnishmentError):
    """Error occurring during a specific garnishment calculation."""
    pass

class InsufficientDataError(GarnishmentError):
    """Error for when required data is missing from the input record."""
    pass


class MultipleGarnishmentPriorityOrder:
    
    
    # --- Constants for Readability and Maintenance ---
    CCPA_LIMIT_PERCENTAGE = 0.25
    
    _CALCULATOR_FACTORIES = {
        GT.CHILD_SUPPORT: lambda record, config_data=None: MultipleGarnishmentPriorityHelper().child_support_helper(record),
        GT.FEDERAL_TAX_LEVY: lambda record, config_data=None: FederalTax().calculate(record,config_data[GT.FEDERAL_TAX_LEVY]),
        GT.SPOUSAL_AND_MEDICAL_SUPPORT: lambda record, config_data=None: WithholdingProcessor().calculate(record),
        GT.CHILD_SUPPORT_AMOUNT: lambda record, config_data=None: WithholdingProcessor().calculate( record),
        GT.BANKRUPTCY_AMOUNT: lambda record, config_data=None: Bankruptcy().calculate(record, config_data=config_data.get(GT.BANKRUPTCY)),
        GT.FRANCHISE_TAX_BOARD : lambda record, config_data=None: FTB().calculate(record, config_data[GT.FRANCHISE_TAX_BOARD]),
        GT.BANKRUPTCY: lambda record, config_data=None: Bankruptcy().calculate(record, config_data=config_data.get(GT.BANKRUPTCY)),
        GT.STUDENT_DEFAULT_LOAN: lambda record, config_data=None: StudentLoanCalculator().calculate(record),
        GT.STATE_TAX_LEVY: lambda record, config_data=None: StateTaxLevyCalculator().calculate(record, config_data=config_data.get(GT.STATE_TAX_LEVY)),
        GT.CREDITOR_DEBT: lambda record, config_data=None: CreditorDebtCalculator().calculate(record, config_data=config_data.get(GT.CREDITOR_DEBT)),
    }

    def __init__(self, record: Dict[str, Any],config_data :Dict[str,Any]):

        if not isinstance(record, dict):
            raise InsufficientDataError("Input 'record' must be a dictionary.")
            
        self.record = record
        self.config_data=config_data
        self.work_state = self.record.get(EE.WORK_STATE)

        
        if not self.work_state:
            raise InsufficientDataError("Required field 'work_state' is missing from the record.")

        # Instantiate helpers that will be used across methods
        self.cs_helper = ChildSupportHelper(self.work_state)
        self.mg_helper = MultipleGarnishmentPriorityHelper()
        self.finance =FinanceUtils()


    def _get_priority_order(self) -> List[Dict[str, Any]]:
        try:
            work_state_name = StateAbbreviations(self.work_state).get_state_name_and_abbr()
            if not work_state_name:
                raise ValueError("Could not resolve state name from abbreviation.")
            
            
            pri_order_qs = MultipleGarnPriorityOrders.objects.select_related('state', 'garnishment_type').filter(
                state__state__iexact=work_state_name
            ).order_by('priority_order')
            
            if not pri_order_qs.exists():
                logger.warning(f"No priority order found for state: {self.work_state}")
                return []
                
            serializer = MultipleGarnPriorityOrderCRUDSerializer(pri_order_qs, many=True)
            return serializer.data
        
        except Exception as e:
            # Catch specific ORM/serializer errors if possible, e.g., ValidationError
            logger.error(f"Error in MultipleGarnishmentPriorityOrder._get_priority_order: {str(e)}\n{t.format_exc()}")
            logger.error(f"Failed to fetch priority order for state '{self.work_state}': {e}")
            raise PriorityOrderError(f"Database error fetching priority order for {self.work_state}.") from e

    def _get_calculator(self, garnishment_type: str) -> Optional[callable]:

        factory = self._CALCULATOR_FACTORIES.get(garnishment_type.lower())
        
        if not factory:
            return None
        
        return lambda: factory(self.record,self.config_data)

    def _prepare_calculation_inputs(self) -> Dict[str, Any]:

        try:
            wages = self.record.get(CF.WAGES, 0)
            commission_and_bonus = self.record.get(CF.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = self.record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = self.record.get(PT.PAYROLL_TAXES)

            gross_pay = self.cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = self.cs_helper.calculate_md(payroll_taxes)
            disposable_earnings = self.cs_helper.calculate_de(gross_pay, mandatory_deductions)

            if disposable_earnings is None:
                raise InsufficientDataError("'disposable_earnings' could not be calculated.")

            return {
                "disposable_earnings": float(disposable_earnings),
                "garnishment_orders": self.record.get("garnishment_orders", []),
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid financial data in record for state '{self.work_state}': {e}")
            raise InsufficientDataError("Invalid or missing financial data in record.") from e

    from decimal import Decimal, InvalidOperation

    def _sum_numeric_values(self, data):
        total = Decimal("0")
        if isinstance(data, dict):
            for v in data.values():
                total += self._sum_numeric_values(v)
        else:
            try:
                # Skip None values and non-numeric types
                if data is None:
                    return float(total)
                # Attempt to convert to Decimal only if it's a number
                if isinstance(data, (int, float, Decimal)):
                    total += Decimal(str(data))
            except (ValueError, TypeError):
                # Skip non-numeric values silently
                pass
        return float(total)

    def _process_deduction_details(self, deduction_details, available_amount):
        """
        Process deduction details to apply priority-based deduction logic.
        
        Args:
            deduction_details: List of deduction details with ordered_amount
            available_amount: Amount available for garnishment
            
        Returns:
            Updated deduction_details with deducted_amount, remaining_balance, 
            fully_deducted, and amount_left_for_other_garn for ALL details
        """
        updated_details = []
        remaining_funds = available_amount
        
        for detail in deduction_details:
            ordered_amount = detail.get('ordered_amount', 0)
            priority_order = detail.get('priority_order', 0)
            
            # Determine how much can be deducted
            if remaining_funds >= ordered_amount:
                deducted_amount = ordered_amount
                remaining_balance = 0
                fully_deducted = True
                remaining_funds -= deducted_amount
            else:
                # If no funds left, set deducted amount to 0 but still process the detail
                deducted_amount = max(0, remaining_funds)
                remaining_balance = ordered_amount - deducted_amount
                fully_deducted = False
                remaining_funds = 0
            
            # Create updated detail
            updated_detail = dict(detail)
            updated_detail['deducted_amount'] = deducted_amount
            updated_detail['remaining_balance'] = remaining_balance
            updated_detail['fully_deducted'] = fully_deducted
            updated_detail['amount_left_for_other_garn'] = remaining_funds
            updated_details.append(updated_detail)
        
        return updated_details, remaining_funds


    def calculate(self) -> Dict[str, Any]:
        """
        Calculate multiple garnishments based on priority order.
        
        Key Logic:
        1. Process garnishments in priority order (from database)
        2. For each garnishment, compare available_for_garnishment with ordered amount
        3. If sufficient funds: deduct fully and continue to next priority
        4. If insufficient funds: deduct partially and set remaining priorities to 0
        5. Track amount_left_for_other_garn for each garnishment result
        
        Returns:
            Dict containing garnishment results with amount_left_for_other_garn field
        """
        
        try:
            inputs = self._prepare_calculation_inputs()
            disposable_earnings = inputs["disposable_earnings"]
            garnishment_orders = inputs["garnishment_orders"]
            
            if not garnishment_orders or not isinstance(garnishment_orders, list):
                logger.info("No garnishment orders found in record. Nothing to calculate.")
                return {"success": False, "status": "No garnishment orders provided.", "error_type": "NoGarnishmentOrders"}
            
            priority_list = self._get_priority_order()
        except GarnishmentError as e:
            logger.error(f"Halting calculation due to a setup error: {e}")
            return {"success": False, "error": str(e), "error_type": type(e).__name__}
        except Exception as e:
            logger.exception(f"Unexpected error preparing calculation inputs for state '{self.work_state}'")
            return {"success": False, "error": str(e), "error_type": type(e).__name__}
        
        twenty_five_percent_of_de = round(self.CCPA_LIMIT_PERCENTAGE * disposable_earnings, 1)

        available_for_garnishment = twenty_five_percent_of_de
        garnishment_results = {}
        
        # --- Prepare the list of garnishments to process ---
        active_order_types = {g_type.strip().lower() for g_type in garnishment_orders}
        skip_types = set()
        # Special handling for child_support and spousal_and_medical_support
        # If both are present, skip child_support and only process spousal_and_medical_support
        if (GT.CHILD_SUPPORT.lower() in active_order_types and 
            GT.SPOUSAL_AND_MEDICAL_SUPPORT.lower() in active_order_types):
            skip_types.add(GT.CHILD_SUPPORT.lower())
            logger.info("Both child_support and spousal_and_medical_support present. Skipping child_support.")
        
        applicable_orders = sorted(
            [
                item for item in priority_list
                if item.get('garnishment_type', '').strip().lower() in active_order_types and
                   item.get('garnishment_type', '').strip().lower() not in skip_types
            ],
            key=lambda x: x.get('priority_order', float('inf'))
        )
        # --- Main Calculation Loop ---
        for item in applicable_orders:
            g_type = item.get('garnishment_type', '').strip().lower()
            if not g_type:
                continue

            # Check if no funds available for garnishment
            if available_for_garnishment <= 0:
                garnishment_results[g_type] = {
                    "withholding_amt": 0,
                    "calculation_status": "skipped_due_to_insufficient_fund",
                    "amount_left_for_other_garn": 0.0
                }
                continue

            try:
                calculator_fn = self._get_calculator(g_type)
                if not calculator_fn:
                    logger.warning(f"No calculator found for type '{g_type}'.")
                    garnishment_results[g_type] = {
                        "withholding_amt": 0, 
                        "calculation_status": "calculator_missing",
                        "amount_left_for_other_garn": available_for_garnishment
                    }
                    continue
                
                # Execute the calculation
                result = calculator_fn()
                # --- Process the result based on garnishment type ---
                amount_withheld = 0
                processed_result = {}


                if g_type == GT.CHILD_SUPPORT:
                    #processed_result = self.mg_helper.distribute_child_support_amount(result, available_for_garnishment)
                    processed_result= self.finance._convert_result_structure(result)
                    processed_result["ade"]=result["ade"]
                    processed_result["de"]=result["de"]
                    processed_result["calculation_status"] = "completed"
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    processed_result["twenty_five_percent_of_de"] = twenty_five_percent_of_de
                    amount_withheld = round(sum(processed_result.get("result_amt", {}).values()) + sum(processed_result.get("arrear_amt", {}).values()), 1)
                    # Update available_for_garnishment based on child support calculation

                    if "amount_left_for_other_garn" in result:
                        available_for_garnishment = round(float(result["amount_left_for_other_garn"]), 1)
                    else:
                        available_for_garnishment -= amount_withheld

                    
                    # Ensure available_for_garnishment doesn't go below 0
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)

                elif g_type == GT.STUDENT_DEFAULT_LOAN:
                    processed_result = self.mg_helper.distribute_student_loan_amount(result, available_for_garnishment)
                    processed_result= self.finance._convert_result_structure(processed_result)
                    amount_withheld = round(sum(processed_result.get("student_loan_amt", {}).values()), 1)
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld 
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)
                elif g_type == GT.CREDITOR_DEBT:
                    if isinstance(result, tuple):
                        result = result[0]
                    base_amount = result.get("withholding_amt", 0)
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    result["withholding_amt"] = amount_withheld
                    processed_result = result
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    processed_result["calculation_status"] = "completed"
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)

                elif g_type == GT.FRANCHISE_TAX_BOARD:
                    processed_result = self.finance._convert_result_structure(result)
                    base_amount = processed_result.get("withholding_amt")
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)
                
                elif g_type == GT.BANKRUPTCY:
                    processed_result = self.finance._convert_result_structure(result)
                    base_amount = processed_result.get("withholding_amt")
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)
                
                elif g_type == GT.FEDERAL_TAX_LEVY:
                    processed_result = self.finance._convert_result_structure(result)
                    base_amount = processed_result.get("withholding_amt")
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)

                elif g_type == GT.STATE_TAX_LEVY:
                    processed_result = self.finance._convert_result_structure(result)
                    base_amount = processed_result.get("withholding_amt")
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)

                elif g_type == GT.SPOUSAL_AND_MEDICAL_SUPPORT:
                    # Handle the spousal_and_medical_support result structure
                    if isinstance(result, dict) and result.get('success'):
                        # Process deduction details with priority-based logic
                        deduction_details = result.get('deduction_details', [])
                        updated_deduction_details, remaining_funds = self._process_deduction_details(
                            deduction_details, available_for_garnishment
                        )
                        
                        # Calculate total amount withheld
                        total_withheld = round(sum(d['deducted_amount'] for d in updated_deduction_details), 1)
                        
                        # Format the result to preserve all calculation details
                        processed_result = {
                            "success": result.get('success', True),
                            "employee_info": result.get('employee_info', {}),
                            "calculations": result.get('calculations', {}),
                            "deduction_details": updated_deduction_details,
                            "summary": result.get('summary', {}),
                            "withholding_amt": total_withheld,
                            "current_amount_withheld": available_for_garnishment,
                            "calculation_status": "completed"
                        }
                        
                        # Update available funds and track remaining amount
                        available_for_garnishment = round(remaining_funds, 1)
                        processed_result["amount_left_for_other_garn"] = available_for_garnishment
                        
                    else:
                        # Fallback for unexpected result structure - preserve all data
                        if isinstance(result, dict):
                            processed_result = dict(result)  # Make a copy to preserve all data
                            processed_result["calculation_status"] = "completed"
                            processed_result["current_amount_withheld"] = available_for_garnishment
                            
                            # Extract withholding amount from various possible locations
                            if 'calculations' in result and 'total_withholding_amount' in result['calculations']:
                                amount_withheld = round(min(result['calculations']['total_withholding_amount'], available_for_garnishment), 1)
                            elif 'withholding_amt' in result:
                                amount_withheld = round(min(result['withholding_amt'], available_for_garnishment), 1)
                            else:
                                amount_withheld = round(self._sum_numeric_values(result.get('calculations', {})), 1)
                            processed_result["withholding_amt"] = amount_withheld
                            
                            # Update available funds and track remaining amount
                            available_for_garnishment -= amount_withheld
                            available_for_garnishment = max(0, available_for_garnishment)
                            processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)
                        else:
                            # If result is not a dict, use finance utility to convert
                            processed_result = self.finance._convert_result_structure(result) if result else {}
                            processed_result["calculation_status"] = "completed"
                            processed_result["current_amount_withheld"] = available_for_garnishment
                            amount_withheld = round(sum(processed_result.get("withholding_amt", {}).values()), 1) if isinstance(processed_result.get("withholding_amt"), dict) else 0
                            processed_result["withholding_amt"] = amount_withheld
                            
                            # Update available funds and track remaining amount
                            available_for_garnishment -= amount_withheld
                            available_for_garnishment = max(0, available_for_garnishment)
                            processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)
                

                else: 
                    base_amount = self._sum_numeric_values(result) if isinstance(result, dict) else 0
                    amount_withheld = round(min(base_amount, available_for_garnishment), 1) if base_amount > 0 else 0
                    processed_result = {"withholding_amt": amount_withheld}
                    processed_result["twenty_five_percent_of_de"] = twenty_five_percent_of_de
                    processed_result["calculation_status"] = "completed"
                    
                    # Update available funds and track remaining amount
                    available_for_garnishment -= amount_withheld
                    available_for_garnishment = max(0, available_for_garnishment)
                    processed_result["amount_left_for_other_garn"] = round(available_for_garnishment, 1)

                garnishment_results[g_type] = processed_result

            except Exception as e:
                logger.exception(f"Error calculating garnishment '{g_type}' for state '{self.work_state}'.")
                garnishment_results[g_type] = {
                    "withholding_amt": 0, 
                    "calculation_status": "calculation_error", 
                    "error_details": str(e),
                    "amount_left_for_other_garn": available_for_garnishment
                }
        garnishment_results["twenty_five_percent_of_de"] = round(twenty_five_percent_of_de, 1)
        garnishment_results["disposable_earning"] = round(disposable_earnings, 1)
        garnishment_results["success"] = True
        return garnishment_results