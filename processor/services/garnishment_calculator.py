"""
Individual garnishment calculation handlers.
Contains specific calculation logic for each garnishment type.
"""

import logging
from typing import Dict, Any, List, Set
from processor.garnishment_library.calculations import (
    ChildSupport, FederalTax, StudentLoanCalculator, StateTaxLevyCalculator,
    CreditorDebtCalculator, Bankruptcy, FTB, WithholdingProcessor,
    MultipleGarnishmentPriorityOrder
)
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    CalculationMessages as CM,
    CommonConstants,
    GarnishmentResultFields as GRF,
    ConfigDataKeys as CDK,
    ErrorMessages as EM,
    CalculationResultKeys as CRK,
    GarnishmentDataKeys as GDK
)
from processor.services.fee_calculator import FeeCalculator
logger = logging.getLogger(__name__)


class GarnishmentCalculator:
    """
    Service class containing individual calculation handlers for each garnishment type.
    """

    def __init__(self, fee_calculator):
        self.fee_calculator = FeeCalculator()
        self.logger = logger

    def calculate_child_support(self, record: Dict, config_data: Dict = None, 
                               garn_fees: float = None) -> Dict:
        """
        Calculate child support garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            calculation_result = ChildSupport(work_state).calculate(record)
            
            child_support_data = calculation_result[CRK.RESULT_AMT]
            arrear_amount_data = calculation_result[CRK.ARREAR_AMT]
            ade, de, mde = calculation_result[CRK.ADE], calculation_result[CRK.DE], calculation_result[CRK.MDE]
            
            total_withhold_amt = sum(child_support_data.values()) + sum(arrear_amount_data.values())
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, total_withhold_amt, garn_fees)
            
            # Create and format result directly
            result = self.create_standardized_result(GT.CHILD_SUPPORT, record)
            
            total_withhold_amt = sum(child_support_data.values()) + sum(arrear_amount_data.values())
            
            if total_withhold_amt <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
            else:
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_withhold_amt, 2)
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(total_withhold_amt, 2)
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} child support: {e}")
            return self.create_standardized_result(
                GT.CHILD_SUPPORT, record, error_message=f"{EM.ERROR_CALCULATING} child support: {e}")

    def calculate_federal_tax(self, record: Dict, config_data: Dict, 
                             garn_fees: float = None) -> Dict:
        """
        Calculate federal tax garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)

            calculation_result = FederalTax().calculate(record, config_data[GT.FEDERAL_TAX_LEVY])
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, calculation_result, garn_fees)
            
            # Create and format result directly
            result = self.create_standardized_result(GT.FEDERAL_TAX_LEVY, record)
            
            if calculation_result == 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
            else:
                withholding_amount = round(calculation_result.get("withholding_amt", 0), 2)
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.FEDERAL_TAX_LEVY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = CM.NA
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = CM.NA
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} federal tax: {e}")
            return self.create_standardized_result(
                GT.FEDERAL_TAX_LEVY, record, error_message=f"{EM.ERROR_CALCULATING} federal tax: {e}")

    def calculate_student_loan(self, record: Dict, config_data: Dict = None, 
                              garn_fees: float = None) -> Dict:
        """
        Calculate student loan garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            case_id = garnishment_data[0].get("data")[0].get("case_id") 
            
            result = StudentLoanCalculator().calculate(record)
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(record)
            loan_amt = result[CRK.STUDENT_LOAN_AMT]

            # Calculate total student loan amount
            total_student_loan_amt = 0 if any(isinstance(val, str) for val in loan_amt.values()) else sum(loan_amt.values())
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, total_student_loan_amt, garn_fees)
            
            # Create and format result directly
            formatted_result = self.create_standardized_result(GT.STUDENT_DEFAULT_LOAN, record)
            
            total_student_loan_amt = 0
            withholding_amounts = []
            
            if isinstance(loan_amt, dict):
                for key, amount in loan_amt.items():
                    if isinstance(amount, (int, float)):
                        withholding_amounts.append({
                            GRF.AMOUNT: round(amount, 2), 
                            GRF.TYPE: GRF.STUDENT_LOAN,
                            GRF.CASE_ID: case_id
                        })
                        total_student_loan_amt += amount
                    else:
                        withholding_amounts.append({
                            GRF.AMOUNT: EM.INSUFFICIENT_PAY, 
                            GRF.TYPE: GRF.STUDENT_LOAN,
                            GRF.CASE_ID: case_id
                        })
            elif isinstance(loan_amt, (int, float)):
                withholding_amounts.append({
                    GRF.AMOUNT: round(loan_amt, 2), 
                    GRF.TYPE: GRF.STUDENT_LOAN,
                    GRF.CASE_ID: case_id
                })
                total_student_loan_amt = loan_amt
            else:
                withholding_amounts.append({
                    GRF.AMOUNT: EM.INSUFFICIENT_PAY, 
                    GRF.TYPE: GRF.STUDENT_LOAN,
                    GRF.CASE_ID: case_id
                })

            if total_student_loan_amt <= 0:
                formatted_result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                formatted_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
            else:
                formatted_result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_student_loan_amt, 2)
                formatted_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount

            formatted_result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
            formatted_result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(
                result[CRK.DISPOSABLE_EARNING], 2)
            formatted_result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(
                total_mandatory_deduction_val, 2)
            formatted_result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = CM.NA
            formatted_result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = CM.NA
            
            return formatted_result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} student loan: {e}")
            return self.create_standardized_result(
                GT.STUDENT_DEFAULT_LOAN, record, error_message=f"{EM.ERROR_CALCULATING} student loan: {e}")

    def calculate_state_tax_levy(self, record: Dict, config_data: Dict = None, 
                                garn_fees: float = None) -> Dict:
        """
        Calculate state tax levy garnishment with standardized result structure.
        """
        try:
            state_tax_view = StateTaxLevyCalculator()
            work_state = record.get(EE.WORK_STATE)
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            calculation_result = state_tax_view.calculate(record, config_data[GT.STATE_TAX_LEVY])
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            if calculation_result == CommonConstants.NOT_FOUND:
                return self.create_standardized_result(
                    GT.STATE_TAX_LEVY, record, error_message=f"State tax levy {EM.CONFIGURATION_NOT_FOUND}")
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, calculation_result[CR.WITHHOLDING_AMT], garn_fees)
            
            # Create result structure
            result = self.create_standardized_result(GT.STATE_TAX_LEVY, record)
            
            if isinstance(calculation_result, dict) and calculation_result.get(CR.WITHHOLDING_AMT, 0) <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result.get(CR.DISPOSABLE_EARNING, 0), 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = round(calculation_result[CR.WITHHOLDING_AMT], 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.STATE_TAX_LEVY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} state tax levy: {e}")
            return self.create_standardized_result(
                GT.STATE_TAX_LEVY, record, error_message=f"{EM.ERROR_CALCULATING} state tax levy: {e}")

    def calculate_creditor_debt(self, record: Dict, config_data: Dict = None, 
                               garn_fees: float = None) -> Dict:
        """
        Calculate creditor debt garnishment with standardized result structure.
        
        """
        try:
            creditor_debt_calculator = CreditorDebtCalculator()
            work_state = record.get(EE.WORK_STATE)
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            data = garnishment_data[0].get(GDK.DATA, [])
            case_id = data[0].get("case_id") if data else None
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            calculation_result = creditor_debt_calculator.calculate(record, config_data[GT.CREDITOR_DEBT])
            print("calculation_result:", calculation_result)
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self.create_standardized_result(
                    GT.CREDITOR_DEBT, record, error_message=f"Creditor debt {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self.create_standardized_result(
                    GT.CREDITOR_DEBT, record, error_message=f"Creditor debt {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, calculation_result[CR.WITHHOLDING_AMT], garn_fees)
            
            # Create result structure
            result = self.create_standardized_result(GT.CREDITOR_DEBT, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: EM.INSUFFICIENT_PAY, GRF.CASE_ID: case_id}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.CASE_ID: case_id}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})

                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount

            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} creditor debt: {e}")
            return self.create_standardized_result(
                GT.CREDITOR_DEBT, record, error_message=f"{EM.ERROR_CALCULATING} creditor debt: {e}")

    def calculate_bankruptcy(self, record: Dict, config_data: Dict = None, 
                             garn_fees: float = None) -> Dict:
        """
        Calculate bankruptcy garnishment with standardized result structure.
        """
        try:
            bankruptcy_calculator = Bankruptcy()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            calculation_result = bankruptcy_calculator.calculate(record, config_data[CDK.BANKRUPTCY])
            
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self.create_standardized_result(
                    GT.BANKRUPTCY, record, error_message=f"Bankruptcy {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self.create_standardized_result(
                    GT.BANKRUPTCY, record, error_message=f"Bankruptcy {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, calculation_result[CR.WITHHOLDING_AMT], garn_fees)
            
            # Create result structure
            result = self.create_standardized_result(GT.BANKRUPTCY, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.BANKRUPTCY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} bankruptcy: {e}")
            return self.create_standardized_result(
                GT.BANKRUPTCY, record, error_message=f"{EM.ERROR_CALCULATING} bankruptcy: {e}")

    def calculate_ftb(self, record: Dict, config_data: Dict, garn_fees: float = None) -> Dict:
        """
        Calculate FTB EWOT/Court/Vehicle garnishment with standardized result structure.
        """
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            if not garnishment_data:
                return None
                
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "").strip().lower()

            # Check if the config exists for this type
            if garnishment_type not in config_data:
                self.logger.error(f"Config data for '{garnishment_type}' is missing. Available keys: {list(config_data.keys())}")
                return self.create_standardized_result(
                    garnishment_type, record,
                    error_message=f"{EM.CONFIG_DATA_MISSING} '{garnishment_type}' {EM.CONFIG_DATA_MISSING_END}")

            creditor_debt_calculator = FTB()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            calculation_result = creditor_debt_calculator.calculate(record, config_data[garnishment_type])
            
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self.create_standardized_result(
                    garnishment_type, record,
                    error_message=f"{garnishment_type} {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self.create_standardized_result(
                    garnishment_type, record,
                    error_message=f"{garnishment_type} {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Calculate garnishment fees
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, calculation_result[CR.WITHHOLDING_AMT], garn_fees)
            
            # Create result structure
            result = self.create_standardized_result(garnishment_type, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: garnishment_type}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} {garnishment_type}: {e}")
            return self.create_standardized_result(
                garnishment_type, record,
                error_message=f"{EM.ERROR_CALCULATING} {garnishment_type}: {e}")

    def calculate_spousal_and_medical_support(self, record: Dict, config_data: Dict = None, 
                                            garn_fees: float = None) -> Dict:
        """
        Calculate spousal and medical support garnishment with standardized result structure.
        """
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)

            
            if not garnishment_data:
                return None
                
            case_id = garnishment_data[0]['data'][0]['case_id']
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "").strip().lower()
            work_state = record.get(EE.WORK_STATE)
            
            child_support_priority = WithholdingProcessor()
            calculation_result = child_support_priority.calculate(record)
            
            # Get total withholding amount for garnishment fee calculation
            total_withholding_amount = calculation_result.get('calculations', {}).get('total_withholding_amount', 0)
            garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, total_withholding_amount, garn_fees)
            
            # Create standardized result
            result = self.create_standardized_result(GT.SPOUSAL_AND_MEDICAL_SUPPORT, record)
            
            # Map calculation data to standardized structure
            calculations = calculation_result.get('calculations', {})
            deduction_details = calculation_result.get('deduction_details', [])
            
            # Update calculation metrics
            result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = calculations.get('disposable_earnings', 0.0)
            result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = calculations.get('allowable_disposable_earnings', 0.0)
            result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = calculations.get('total_withholding_amount', 0.0)
            
            # Update garnishment details
            result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = calculations.get('total_withholding_amount', 0.0)
            result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = calculations.get('total_withholding_amount', 0.0)
            
            # Map withholding amounts from deduction details
            withholding_amounts = []
            arrear_amounts = []
            
            for deduction in deduction_details:
                deduction_type = deduction.get('deduction_type', '')
                deducted_amount = deduction.get('deducted_amount', 0.0)
                
                if deducted_amount > 0:
                    if 'arrear' in deduction_type.lower():
                        arrear_amounts.append({
                            GRF.CASE_ID: case_id,
                            GRF.AMOUNT: deducted_amount,
                            GRF.DEDUCTION_TYPE: deduction_type
                        })
                    else:
                        withholding_amounts.append({
                            GRF.CASE_ID: case_id,
                            GRF.AMOUNT: deducted_amount,
                            GRF.DEDUCTION_TYPE: deduction_type
                        })
            
            result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
            result[GRF.GARNISHMENT_DETAILS][GRF.ARREAR_AMOUNTS] = arrear_amounts
            
            # Update garnishment fees
            result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            
            # Add original calculation details for backward compatibility
            result['original_calculation'] = calculation_result
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} spousal and medical support: {e}")
            return self.create_standardized_result(
                GT.SPOUSAL_AND_MEDICAL_SUPPORT, record, 
                error_message=f"{EM.ERROR_CALCULATING} spousal and medical support: {e}")

    def calculate_multiple_garnishment(self, record: Dict, config_data: Dict, 
                                     garn_fees: float = None) -> Dict:
        """
        Calculate multiple garnishment with standardized result structure.
        """
        try:
            # Prepare record for multiple garnishment calculation
            prepared_record = record.copy()
            prepared_record[GDK.GARNISHMENT_ORDERS] = record.get(GDK.GARNISHMENT_ORDERS, [])
            
            multiple_garnishment = MultipleGarnishmentPriorityOrder(prepared_record, config_data)
            calculation_result = multiple_garnishment.calculate()

            if calculation_result == CommonConstants.NOT_FOUND:
                result = self.create_standardized_result("multiple_garnishment", record)
                result[GRF.CALCULATION_STATUS] = GRF.NOT_FOUND
                result[GRF.ERROR] = EM.NO_GARNISHMENT_CONFIGURATION
                return result
                
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                result = self.create_standardized_result("multiple_garnishment", record)
                result[GRF.CALCULATION_STATUS] = GRF.NOT_PERMITTED
                result[GRF.ERROR] = EM.GARNISHMENT_NOT_PERMITTED_CASE
                return result
            
            # Use result formatter for multiple garnishment
            work_state = record.get(EE.WORK_STATE)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            total_withheld = 0.0
            garnishment_types = []
            
            # Process each garnishment type from the calculation results
            for garnishment_type, type_result in calculation_result.items():
                if isinstance(type_result, dict):
                    # Calculate garnishment fees for this type
                    type_withholding_amount = type_result.get(CR.WITHHOLDING_AMT, 0)
                    garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                        work_state, garnishment_type, pay_period, type_withholding_amount, garn_fees)
                    
                    garnishment_result = {
                        GRF.GARNISHMENT_TYPE: garnishment_type,
                        GRF.WITHHOLDING_AMOUNTS: [{
                            GRF.AMOUNT: round(type_withholding_amount, 2),
                            GRF.TYPE: garnishment_type
                        }],
                        GRF.TOTAL_WITHHELD: round(type_withholding_amount, 2),
                        GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                        GRF.GARNISHMENT_FEES: garnishment_fees_amount,
                        CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0)
                    }
                    
                    garnishment_types.append(garnishment_result)
                    total_withheld += type_withholding_amount
            
            # Create final result
            result = self.create_standardized_result("multiple_garnishment", record)
            result["garnishment_types"] = garnishment_types
            result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_withheld, 2)
            result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = total_withheld
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")
            return self.create_standardized_result(
                "multiple_garnishment", record, 
                error_message=f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")

    def create_standardized_result(self, garnishment_type: str, record: Dict, 
                                 calculation_result: Dict = None, error_message: str = None) -> Dict:
        """
        Creates a standardized result structure for garnishment calculations.
        This ensures consistency across all garnishment types.
        """
        result = {
            GRF.GARNISHMENT_TYPE: garnishment_type,
            GRF.EMPLOYEE_ID: record.get(EE.EMPLOYEE_ID),
            GRF.WORK_STATE: record.get(EE.WORK_STATE),
            GRF.CALCULATION_STATUS: GRF.SUCCESS if not error_message else GRF.ERROR,
            GRF.GARNISHMENT_DETAILS: {
                GRF.WITHHOLDING_AMOUNTS: [],
                GRF.ARREAR_AMOUNTS: [],
                GRF.TOTAL_WITHHELD: 0.0,
                GRF.NET_WITHHOLDING: 0.0
            },
            GRF.CALCULATION_METRICS: {
                GRF.DISPOSABLE_EARNINGS: 0.0,
                GRF.ALLOWABLE_DISPOSABLE_EARNINGS: 0.0,
                GRF.TOTAL_MANDATORY_DEDUCTIONS: 0.0,
                GRF.WITHHOLDING_BASIS: CM.NA,
                GRF.WITHHOLDING_CAP: CM.NA,
                GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
            },
            CR.ER_DEDUCTION: {
                GRF.GARNISHMENT_FEES: 0.0
            }
        }
        
        if error_message:
            result[GRF.ERROR] = error_message
            result[GRF.CALCULATION_STATUS] = GRF.ERROR
            
        return result
