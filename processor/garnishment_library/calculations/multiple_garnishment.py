import logging
from typing import Any, Dict, List, Optional
from processor.garnishment_library.utils import StateAbbreviations,MultipleGarnishmentPriorityHelper,FinanceUtils
from processor.garnishment_library.utils.response import CalculationResponse as CR
from .federal_case import FederalTax
from processor.garnishment_library.calculations import (StateTaxLevyCalculator, 
                                                        FederalTax, ChildSupport, StudentLoanCalculator, ChildSupport,ChildSupportHelper,CreditorDebtCalculator)
from user_app.constants import (
    EmployeeFields as EE,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    GarnishmentTypeFields as GT,

)
from processor.serializers import MultipleGarnPriorityOrderCRUDSerializer
from decimal import Decimal
import traceback as t 
from processor.models import MultipleGarnPriorityOrders



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
    MAX_CALCULATED_GARNISHMENTS = 2
    CCPA_LIMIT_PERCENTAGE = 0.25
    
    _CALCULATOR_FACTORIES = {
        GT.CHILD_SUPPORT: lambda record, config_data=None: MultipleGarnishmentPriorityHelper().child_support_helper(record),
        GT.FEDERAL_TAX_LEVY: lambda record, config_data=None: FederalTax().calculate(record, config_data=config_data.get(GT.FEDERAL_TAX_LEVY)),
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
            logger.error(f"Failed to fetch priority order for state '{self.work_state}': {e}")
            raise PriorityOrderError(f"Database error fetching priority order for {self.work_state}.") from e

    def _get_calculator(self, garnishment_type: str) -> Optional[callable]:

        factory = self._CALCULATOR_FACTORIES.get(garnishment_type.lower())
        # print("factory",factory(self.record,self.config_data))
        
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
                # Attempt to convert to Decimal only if it's a number
                if isinstance(data, (int, float, Decimal)):
                    total += Decimal(str(data))
            except ( ValueError, TypeError):
                # Skip non-numeric values silently
                pass
        return total


    def calculate(self) -> Dict[str, Any]:

        try:
            inputs = self._prepare_calculation_inputs()
            disposable_earnings = inputs["disposable_earnings"]
            garnishment_orders = inputs["garnishment_orders"]
            
            if not garnishment_orders or not isinstance(garnishment_orders, list):
                logger.info("No garnishment orders found in record. Nothing to calculate.")
                return {"status": "No garnishment orders provided."}
            
            priority_list = self._get_priority_order()
        except GarnishmentError as e:
            logger.error(f"Halting calculation due to a setup error: {e}")
            return {"error": str(e)}
        
        twenty_five_percent_of_de = round(self.CCPA_LIMIT_PERCENTAGE * disposable_earnings, 2)


        available_for_garnishment = twenty_five_percent_of_de
        # print("available_for_garnishment",available_for_garnishment)
        garnishment_results = {}
        
        # --- Prepare the list of garnishments to process ---
        active_order_types = {g_type.strip().lower() for g_type in garnishment_orders}
        skip_types = {GT.FEDERAL_TAX_LEVY.lower(), GT.STATE_TAX_LEVY.lower()}
        
        applicable_orders = sorted(
            [
                item for item in priority_list
                if item.get('garnishment_type', '').strip().lower() in active_order_types and
                   item.get('garnishment_type', '').strip().lower() not in skip_types
            ],
            key=lambda x: x.get('priority_order', float('inf'))
        )
        calculated_count = 0
        # --- Main Calculation Loop ---
        for item in applicable_orders:
            g_type = item.get('garnishment_type', '').strip().lower()
            if not g_type:
                continue

            # Check if we've reached the maximum calculated garnishments limit
            if calculated_count >= self.MAX_CALCULATED_GARNISHMENTS:
                # For remaining types after reaching the limit, return 0 amount
                garnishment_results[g_type] = {"withholding_amt": 0,"calculation_status":"skipped_due_to_insufficient_fund"}
                continue
            # Check if no funds available for garnishment
            if available_for_garnishment <= 0:
                garnishment_results[g_type] = {"withholding_amt": 0,"calculation_status":"skipped_due_to_insufficient_fund"}
                continue

            try:
                calculator_fn = self._get_calculator(g_type)
                if not calculator_fn:
                    logger.warning(f"No calculator found for type '{g_type}'.")
                    garnishment_results[g_type] = {"withholding_amt": 0, "calculation_status": "calculator_missing"}
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
                    amount_withheld = sum(processed_result.get("result_amt", {}).values()) + sum(processed_result.get("arrear_amt", {}).values())
                    available_for_garnishment=float(result["amount_left_for_other_garn"])

                    # If amount_left_for_other_garn is zero, apply the extra check
                    if float(result["amount_left_for_other_garn"]) == 0:
                        diff = round(twenty_five_percent_of_de - amount_withheld, 2)
                        if diff > 0:
                            available_for_garnishment = diff
                        else:
                            available_for_garnishment = 0
                    else:
                        available_for_garnishment = float(result["amount_left_for_other_garn"])

                elif g_type == GT.STUDENT_DEFAULT_LOAN:
                    processed_result = self.mg_helper.distribute_student_loan_amount(result, available_for_garnishment)
                    processed_result= self.finance._convert_result_structure(processed_result)
                    amount_withheld = sum(processed_result.get("student_loan_amt", {}).values())
                    processed_result["calculation_status"] = "completed"
                    processed_result["withholding_amt"] = amount_withheld 
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    
                    # Add this line to update available funds
                    available_for_garnishment -= amount_withheld
                elif g_type == GT.CREDITOR_DEBT:
                    if isinstance(result, tuple):
                        result = result[0]
                    base_amount = result.get("withholding_amt", 0)
                    amount_withheld = min(base_amount, available_for_garnishment) if base_amount > 0 else 0
                    result["withholding_amt"] = amount_withheld
                    processed_result = result
                    processed_result["current_amount_withheld"] = available_for_garnishment
                    processed_result["calculation_status"] = "completed"

                else: 
                    base_amount = self._sum_numeric_values(result) if isinstance(result, dict) else 0
                    amount_withheld = min(base_amount, available_for_garnishment) if base_amount > 0 else 0
                    processed_result = {"withholding_amt": amount_withheld}
                    processed_result["twenty_five_percent_of_de"] = twenty_five_percent_of_de
                    processed_result["calculation_status"] = "completed"



                garnishment_results[g_type] = processed_result
                # available_for_garnishment -= amount_withheld
                calculated_count += 1

            except Exception as e:
                import traceback as t
                print(t.print_exc())
                logger.exception(f"Error calculating garnishment '{g_type}' for state '{self.work_state}'.")
                garnishment_results[g_type] = {"withholding_amt": 0, "calculation_status": "calculation_error", "error_details": str(e)}

                # We still increment count as this counts as a processed attempt
                calculated_count += 1   
         
        return garnishment_results