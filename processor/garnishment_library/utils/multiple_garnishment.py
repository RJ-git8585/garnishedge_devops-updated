import logging
from user_app.constants import (
    AllocationMethods,
    EmployeeFields as EE,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    PayPeriodFields as PP,
    GarnishmentTypeFields as GT
)
from .common import AllocationMethodResolver,ExemptAmount,FinanceUtils
from .child_support import Helper
import traceback as t
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from enum import Enum

FMW_RATE = 7.25
PAY_PERIOD_MULTIPLIER = {
    PP.WEEKLY: 30,
    PP.BI_WEEKLY: 60,
    PP.SEMI_MONTHLY: 65,
    PP.MONTHLY: 130,
}


FMW_RATE = 7.25
PAY_PERIOD_MULTIPLIER = {
    PP.WEEKLY: 30,
    PP.BI_WEEKLY: 60,
    PP.SEMI_MONTHLY: 65,
    PP.MONTHLY: 130,
}



class GarnishmentError(Exception):
    """Base exception for garnishment processing errors."""
    pass

class InvalidStateError(GarnishmentError):
    """Raised when an invalid state is provided."""
    pass

class CalculationError(GarnishmentError):
    """Raised when calculation errors occur."""
    pass

class DataValidationError(GarnishmentError):
    """Raised when input data validation fails."""
    pass




class MultipleGarnishmentPriorityHelper:
    """
    Class to determine the priority order of multiple garnishments based on state rules.
    Handles child support and student loan garnishment calculations with proper error handling.
    """
    
    def __init__(self):
        """Initialize the helper with logging configuration."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _validate_numeric_input(self, value: Any, field_name: str, allow_negative: bool = False) -> Decimal:
        """
        Validate and convert numeric input to Decimal.
        
        """
        try:
            if value is None:
                return Decimal('0')
            
            decimal_value = Decimal(str(value))
            
            if not allow_negative and decimal_value < 0:
                raise DataValidationError(f"{field_name} cannot be negative: {value}")
                
            return decimal_value
            
        except (TypeError, ValueError, ArithmeticError) as e:
            raise DataValidationError(f"Invalid numeric value for {field_name}: {value}. Error: {e}")
    
    def _validate_distribution_input(self, result: Dict, available_amount: Union[int, float, Decimal]) -> Decimal:
        """
        Validate input parameters for distribution methods.
        
        """
        # Handle None result by returning empty structure
        if result is None:
            self.logger.warning("Result parameter is None, treating as empty dictionary")
            result = {"result_amt": {}, "arrear_amt": {}}
        
        if not isinstance(result, dict):
            self.logger.error(f"Result type validation failed. Expected dict, got {type(result)}: {result}")
            raise DataValidationError(f"Result must be a dictionary, got {type(result).__name__}")
        
        validated_amount = self._validate_numeric_input(available_amount, "available_amount")
        
        if validated_amount < 0:
            raise DataValidationError("Available amount cannot be negative")
            
        return validated_amount

    def distribute_child_support_amount(self, result: Dict, available_amount: Union[int, float, Decimal]) -> Dict[str, Dict[str, Decimal]]:
        """
        Distributes child support amounts based on available funds.
        Processes result_amt first, then arrear_amt.
        
        """
        try:
            # Handle None result gracefully
            if result is None:
                self.logger.warning("Received None result, returning empty distribution")
                return {
                    "result_amt": {},
                    "arrear_amt": {}
                }
            
            validated_amount = self._validate_distribution_input(result, available_amount)
            
            result_amt = result.get("result_amt", {})
            arrear_amt = result.get("arrear_amt", {})
            
            if not isinstance(result_amt, dict):
                self.logger.warning(f"result_amt is not a dict, got {type(result_amt)}, defaulting to empty dict")
                result_amt = {}
                
            if not isinstance(arrear_amt, dict):
                self.logger.warning(f"arrear_amt is not a dict, got {type(arrear_amt)}, defaulting to empty dict")
                arrear_amt = {}
            
            final_result_amt = {}
            final_arrear_amt = {}
            remaining_amount = validated_amount
            
            # Process result_amt first
            for key, value in result_amt.items():
                try:
                    decimal_value = self._validate_numeric_input(value, f"result_amt[{key}]")
                    
                    if remaining_amount >= decimal_value:
                        final_result_amt[key] = decimal_value
                        remaining_amount -= decimal_value
                    elif remaining_amount > 0:
                        final_result_amt[key] = remaining_amount
                        remaining_amount = Decimal('0')
                    else:
                        final_result_amt[key] = Decimal('0')
                        
                except (DataValidationError, CalculationError) as e:
                    self.logger.warning(f"Error processing result_amt[{key}]: {e}")
                    final_result_amt[key] = Decimal('0')
            
            # Process arrear_amt
            for key, value in arrear_amt.items():
                try:
                    decimal_value = self._validate_numeric_input(value, f"arrear_amt[{key}]")
                    
                    if remaining_amount >= decimal_value:
                        final_arrear_amt[key] = decimal_value
                        remaining_amount -= decimal_value
                    elif remaining_amount > 0:
                        final_arrear_amt[key] = remaining_amount
                        remaining_amount = Decimal('0')
                    else:
                        final_arrear_amt[key] = Decimal('0')
                        
                except (DataValidationError, CalculationError) as e:
                    self.logger.warning(f"Error processing arrear_amt[{key}]: {e}")
                    final_arrear_amt[key] = Decimal('0')
            
            self.logger.info(f"Child support distribution completed. Remaining amount: {remaining_amount}")
            
            return {
                "result_amt": final_result_amt,
                "arrear_amt": final_arrear_amt
            }
            
        except Exception as e:
            self.logger.error(f"Error in distribute_child_support_amount: {e}")
            # Return safe fallback instead of raising exception
            return {
                "result_amt": {},
                "arrear_amt": {}
            }

    def distribute_student_loan_amount(self, result: Dict, available_amount: Union[int, float, Decimal]) -> Dict[str, Dict[str, Decimal]]:
        """
        Distributes student loan amounts based on available funds.
        
        """
        try:
            validated_amount = self._validate_distribution_input(result, available_amount)
            
            student_loan_amt = result.get("student_loan_amt", {})
            
            if not isinstance(student_loan_amt, dict):
                raise DataValidationError("student_loan_amt must be a dictionary")
            
            final_student_loan_amt = {}
            remaining_amount = validated_amount
            
            for key, value in student_loan_amt.items():
                try:
                    decimal_value = self._validate_numeric_input(value, f"student_loan_amt[{key}]")
                    
                    if remaining_amount >= decimal_value:
                        final_student_loan_amt[key] = decimal_value
                        remaining_amount -= decimal_value
                    elif remaining_amount > 0:
                        final_student_loan_amt[key] = remaining_amount
                        remaining_amount = Decimal('0')
                    else:
                        final_student_loan_amt[key] = Decimal('0')
                        
                except (DataValidationError, CalculationError) as e:
                    self.logger.warning(f"Error processing student_loan_amt[{key}]: {e}")
                    final_student_loan_amt[key] = Decimal('0')
            
            self.logger.info(f"Student loan distribution completed. Remaining amount: {remaining_amount}")
            
            return {"student_loan_amt": final_student_loan_amt}
            
        except Exception as e:
            self.logger.error(f"Error in distribute_student_loan_amount: {e}")
            raise CalculationError(f"Failed to distribute student loan amount: {e}")
    
    def _validate_record_data(self, record: Dict) -> None:
        """
        Validate required fields in the record.
        
        """
        required_fields = [EE.WORK_STATE, EE.PAY_PERIOD, EE.EMPLOYEE_ID]
        
        for field in required_fields:
            if field not in record or record[field] is None:
                raise DataValidationError(f"Required field '{field}' is missing or None")
        
        # Validate state
        state_name = record.get(EE.WORK_STATE)
        if not isinstance(state_name, str) or not state_name.strip():
            raise DataValidationError("Work state must be a non-empty string")
        
        # Validate pay period
        pay_period = record.get(EE.PAY_PERIOD.lower())
        if not isinstance(pay_period, str) or not pay_period.strip():
            raise DataValidationError("Pay period must be a non-empty string")
        
        # Validate garnishment data
        garnishment_data = record.get('garnishment_data')
        if garnishment_data is not None and not isinstance(garnishment_data, list):
            raise DataValidationError("Garnishment data must be a list or None")

    def _get_garnishment_amount(self,data, garnishment_type, field):
        """
        Get the total amount (ordered_amount or arrear_amount)
        for a given garnishment type from the dataset.
        
        :param data: list of dicts (your garnishment data)
        :param garnishment_type: str -> e.g. "Child_Support"
        :param field: str -> either "ordered_amount" or "arrear_amount"
        :return: float -> total amount for that type
        """
        for item in data:
            if item["type"].lower() == garnishment_type.lower():
                return [d.get(field, 0.0) for d in item["data"]]
        return 0.0

    def child_support_helper(self, record: Dict) -> Dict:
        """
        Calculate child support garnishment amounts with comprehensive error handling.
        
        """
        try:
            from processor.garnishment_library.calculations.child_support import ChildSupportHelper
            # Validate input data
            if not isinstance(record, dict):
                raise DataValidationError("Record must be a dictionary")
            
            self._validate_record_data(record)

            result={}
            
            # Extract and validate data
            state_name = record.get(EE.WORK_STATE).strip().lower()
            issuing_state = record.get(EE.ISSUING_STATE).strip().lower()
            wages = self._validate_numeric_input(record.get(CF.WAGES, 0), "wages")
            commission_and_bonus = self._validate_numeric_input(record.get(CF.COMMISSION_AND_BONUS, 0), "commission_and_bonus")
            pay_period = record.get(EE.PAY_PERIOD.lower()).strip().lower()
            non_accountable_allowances = self._validate_numeric_input(record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0), "non_accountable_allowances")
            payroll_taxes = record.get(PT.PAYROLL_TAXES, {})
            employee_id = record.get(EE.EMPLOYEE_ID)
            supports_2nd_family = record.get(EE.SUPPORT_SECOND_FAMILY, False)
            arrears_12ws = record.get(EE.ARREARS_GREATER_THAN_12_WEEKS, False)
            garnishment_data = record.get('garnishment_data', [])
            
            self.logger.info(f"Processing child support for employee {employee_id} in state {state_name}")
            
            # Initialize child support helper
            try:
                
                cs_helper = ChildSupportHelper(state_name)
            except ImportError as e:
                raise GarnishmentError(f"Failed to import ChildSupportHelper: {e}")
            except Exception as e:
                raise InvalidStateError(f"Failed to initialize ChildSupportHelper for state '{state_name}': {e}")
            
            # Perform calculations with error handling
            try:
                exempt_amount = ExemptAmount().get_fmw(pay_period)
                gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
                mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
                disposable_earnings = cs_helper.calculate_de(gross_pay, mandatory_deductions)
                withholding_limit = cs_helper.calculate_wl(employee_id, supports_2nd_family, arrears_12ws, disposable_earnings, garnishment_data,issuing_state)
                ade = cs_helper.calculate_ade(withholding_limit, disposable_earnings)
                de_twenty_five_percent = (disposable_earnings*.25)

                # Validate calculated values
                if disposable_earnings < 0:
                    self.logger.warning(f"Negative disposable earnings calculated: {disposable_earnings}")
                    disposable_earnings = 0
                
                diff_of_de_and_exempt_amount = max(disposable_earnings - exempt_amount, 0)
                
            except Exception as e:
                raise CalculationError(f"Error during basic calculations: {e}")
            
            # Get support amounts

            try:

                support_amount = self._get_garnishment_amount(garnishment_data, GT.CHILD_SUPPORT, "ordered_amount")
                arrear_amount = self._get_garnishment_amount(garnishment_data, GT.CHILD_SUPPORT, "arrear_amount")

                
                if not isinstance(support_amount, list):
                    support_amount = []
                if not isinstance(arrear_amount, list):
                    arrear_amount = []
                
            except Exception as e:
                self.logger.warning(f"Error getting support amounts: {e}")
                support_amount, arrear_amount = [], []
            
            # Calculate totals
            total_child_support_amount = sum(support_amount)
            total_arrear_amount = sum(arrear_amount)
            sum_of_order_amount = total_child_support_amount + total_arrear_amount
            total_withholding_amount = min(sum_of_order_amount, diff_of_de_and_exempt_amount, ade)

            
            try:
                withholding_amount = cs_helper.calculate_twa(support_amount, arrear_amount)
                alloc_method = AllocationMethodResolver(state_name).get_allocation_method()

            except Exception as e:
                raise CalculationError(f"Error calculating withholding amount or allocation method: {e}")


            # Calculate final amounts
            try:
                if total_withholding_amount >= sum_of_order_amount:
                    cs_amounts = Helper().calculate_each_amount(support_amount, "child support amount")
                    ar_amounts = Helper().calculate_each_amount(arrear_amount, "arrear amount")
                else:
                    cs_amounts, ar_amounts = self._calculate_prorated_amounts(
                        alloc_method, support_amount, arrear_amount, total_withholding_amount, withholding_amount, gross_pay
                    )

                
            except Exception as e:
                self.logger.error(f"Error calculating final amounts: {e}")
                cs_amounts, ar_amounts = {}, {}
            cs_amounts=FinanceUtils()._convert_result_structure(cs_amounts)
            ar_amounts=FinanceUtils()._convert_result_structure(ar_amounts)
            total_withholding_amount= FinanceUtils()._convert_result_structure({"total_withholding_amount":total_withholding_amount})
            amount_left_for_other_garn = de_twenty_five_percent-total_withholding_amount['total_withholding_amount'] if total_withholding_amount['total_withholding_amount'] > 0 else 0
            result= {
                "result_amt": cs_amounts,
                "arrear_amt": ar_amounts,
                "ade": ade,
                "de": disposable_earnings,
                "mde": mandatory_deductions,
                "amount_left_for_other_garn": amount_left_for_other_garn
            }
        
            
            self.logger.info(f"Child support calculation completed successfully for employee {employee_id}")
            return result
            
        except (DataValidationError, InvalidStateError, CalculationError, GarnishmentError):
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in child_support_helper: {e}")
            raise GarnishmentError(f"Unexpected error processing child support: {e}")
        
    
    def _calculate_prorated_amounts(self, alloc_method, support_amount, arrear_amount, total_withholding_amount, withholding_amount, gross_pay):
        """
        Calculate prorated amounts based on allocation method.
        
        """
        try:
            cs_amounts, ar_amounts = {}, {}
            total_child_support_amount = sum(support_amount)
            total_arrear_amount = sum(arrear_amount)
            
            if alloc_method == AllocationMethods.PRORATE:
                # Prorate support amounts
                if total_child_support_amount > 0:
                    for i, amt in enumerate(support_amount):
                        proportion = amt / total_child_support_amount if total_child_support_amount > 0 else 0
                        cs_amounts[f"child support amount{i+1}"] = (
                            round(float(proportion) * float(total_withholding_amount),2)
                            if gross_pay > 0 else 0
                        )

                
                # Prorate arrear amounts
                arrear_pool = max(total_withholding_amount - total_child_support_amount, 0)
                if total_arrear_amount > 0 and arrear_pool > 0:
                    for i, amt in enumerate(arrear_amount):
                        proportion = amt / total_arrear_amount
                        ar_amounts[f"arrear amount{i+1}"] = (
                            round(proportion * arrear_pool,2)
                            if gross_pay > 0 else 0
                        )
                else:
                    ar_amounts = {f"arrear amount{i+1}": 0 for i in range(len(arrear_amount))}
                    
            elif alloc_method == AllocationMethods.DEVIDEEQUALLY:
                # Divide equally among orders
                if len(support_amount) > 0:
                    split_amt =round(total_withholding_amount / len(support_amount),2)
                    cs_amounts = {
                        f"child support amount{i+1}": split_amt if gross_pay > 0 else 0
                        for i in range(len(support_amount))
                    }
                
                arrear_pool = max(total_withholding_amount - sum(cs_amounts.values()), 0)
                if len(arrear_amount) > 0 and arrear_pool > 0:
                    split_arrear = round(arrear_pool / len(arrear_amount),2)
                    ar_amounts = {
                        f"arrear amount{i+1}": split_arrear if gross_pay > 0 else 0
                        for i in range(len(arrear_amount))
                    }
                else:
                    ar_amounts = {f"arrear amount{i+1}": 0 for i in range(len(arrear_amount))}
            else:
                raise CalculationError(f"Invalid allocation method: {alloc_method}")
                
            return cs_amounts, ar_amounts
            
        except Exception as e:
            raise CalculationError(f"Error calculating prorated amounts: {e}")
        

        