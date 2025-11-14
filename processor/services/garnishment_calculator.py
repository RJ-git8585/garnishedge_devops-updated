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
from processor.garnishment_library.utils.response import UtilityClass, CalculationResponse
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CF,
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
        self.child_support_helper = ChildSupportHelper()


    def calculate_de(self,record: Dict) -> float:
        """
        Calculate disposable earnings.
        """
        try:
            wages=record.get(CF.WAGES, 0)
            commission_and_bonus=record.get(CF.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances=record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            return self.child_support_helper.calculate_de(wages, commission_and_bonus, non_accountable_allowances)
        except Exception as e:
            logger.error(f"Error calculating disposable earnings: {e}")
            return 0

    def get_basis_map(self,gross_pay, net_pay, disposable_earning):

        return {
        # Gross Pay variations
        "gross_pay": gross_pay,
        "gross pay": gross_pay,
        "Gross pay": gross_pay,
        "Gross Pay": gross_pay,
        "GROSS PAY": gross_pay,
        "GROSS_PAY": gross_pay,
        "grosspay": gross_pay,
        "GrossPay": gross_pay,

        # Net Pay variations
        "net_pay": net_pay,
        "net pay": net_pay,
        "Net pay": net_pay,
        "NET PAY": net_pay,
        "NET_PAY": net_pay,
        "netpay": net_pay,
        "NetPay": net_pay,

        # Disposable Earnings variations
        "disposable_earning": disposable_earning,
        "disposable earning": disposable_earning,
        "Disposable earning": disposable_earning,
        "Disposable Earning": disposable_earning,
        "DISPOSABLE EARNING": disposable_earning,
        "DISPOSABLE_EARNING": disposable_earning,
        "disposableearning": disposable_earning,
        "DisposableEarning": disposable_earning,
    }




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
            logger.warning(f"Error extracting case_id for {garnishment_type}: {e}")
            return garnishment_type    


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
            # Use parameter value if provided, otherwise get from record
            if garn_fees is None:
                garn_fees = record.get(EE.GARNISHMENT_FEES, 0)
            
            child_support_data = calculation_result[CRK.RESULT_AMT]
            arrear_amount_data = calculation_result[CRK.ARREAR_AMT]
            ade, de, mde = calculation_result[CRK.ADE], calculation_result[CRK.DE], calculation_result[CRK.MDE]
            
            total_withhold_amt = sum(child_support_data.values()) + sum(arrear_amount_data.values())
            
            # Create standardized result
            result = self.create_standardized_result(GT.CHILD_SUPPORT, record)
            
            if total_withhold_amt <= 0:
                # Handle insufficient pay scenario with case IDs    
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                
                # Get case IDs for insufficient pay scenario
                garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                child_support_garnishment = None
                
                for garnishment in garnishment_data:
                    if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                        child_support_garnishment = garnishment
                        break
                
                if child_support_garnishment:
                    cases = child_support_garnishment.get(GDK.DATA, [])
                    withholding_amounts = []
                    arrear_amounts = []
                    
                    for case in cases:
                        case_id = case.get(EE.CASE_ID, GRF.UNKNOWN_CASE)
                        withholding_amounts.append({
                            GRF.AMOUNT: GRF.INSUFFICIENT_PAY, 
                            GRF.TYPE: GRF.CURRENT_SUPPORT,
                            GRF.CASE_ID: case_id
                        })
                        arrear_amounts.append({
                            GRF.AMOUNT: GRF.INSUFFICIENT_PAY, 
                            GRF.TYPE: GRF.ARREAR,
                            GRF.CASE_ID: case_id
                        })
                    
                    result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
                    result[GRF.GARNISHMENT_DETAILS][0][GRF.ARREAR_AMOUNTS] = arrear_amounts
                else:
                    # Fallback
                    result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                        {GRF.AMOUNT: GRF.INSUFFICIENT_PAY, GRF.TYPE: GRF.CURRENT_SUPPORT} 
                        for _ in child_support_data
                    ]
                    result[GRF.GARNISHMENT_DETAILS][0][GRF.ARREAR_AMOUNTS] = [
                    {GRF.AMOUNT: GRF.INSUFFICIENT_PAY, GRF.TYPE: GRF.ARREAR} 
                    for _ in arrear_amount_data
                    ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
            else:
                # Calculate garnishment fees
                garnishment_fees = self.fee_calculator.get_rounded_garnishment_fee(work_state, garnishment_type, pay_period, total_withhold_amt,garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str):
                    garnishment_fees_amount = garnishment_fees
                
                # Populate withholding amounts with actual case IDs
                withholding_amounts = []
                arrear_amounts = []
                
                # Get garnishment data from input to extract case IDs
                garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                child_support_garnishment = None
                
                # Find child support garnishment data
                for garnishment in garnishment_data:
                    if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                        child_support_garnishment = garnishment
                        break
                
                # Map amounts to case IDs
                if child_support_garnishment:
                    cases = child_support_garnishment.get(GDK.DATA, [])
                    child_support_amounts = list(child_support_data.values())
                    arrear_amounts_list = list(arrear_amount_data.values())
                    
                    for idx, case in enumerate(cases):
                        case_id = case.get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{idx}")
                        
                        # Add current support amount
                        if idx < len(child_support_amounts):
                            withholding_amounts.append({
                                GRF.AMOUNT: round(child_support_amounts[idx], 2),
                                GRF.TYPE: GRF.CURRENT_SUPPORT,
                                GRF.CASE_ID: case_id
                            })
                        
                        # Add arrear amount
                        if idx < len(arrear_amounts_list):
                            arrear_amounts.append({
                                GRF.AMOUNT: round(arrear_amounts_list[idx], 2),
                                GRF.TYPE: GRF.ARREAR,
                                GRF.CASE_ID: case_id
                            })
                else:
                    # Fallback to case_index if no garnishment data found
                    withholding_amounts = [
                        {GRF.AMOUNT: round(amt, 2), GRF.TYPE: GRF.CURRENT_SUPPORT, GRF.CASE_INDEX: idx}
                        for idx, amt in enumerate(child_support_data.values())
                    ]
                    arrear_amounts = [
                        {GRF.AMOUNT: round(amt, 2), GRF.TYPE: GRF.ARREAR, GRF.CASE_INDEX: idx}
                        for idx, amt in enumerate(arrear_amount_data.values())
                    ]
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
                result[GRF.GARNISHMENT_DETAILS][0][GRF.ARREAR_AMOUNTS] = arrear_amounts
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = round(total_withhold_amt, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = round(total_withhold_amt )
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            return result
            
        except Exception as e:
            import traceback as t
            print(t.print_exc())
            logger.error(f"{EM.ERROR_CALCULATING} child support: {e}")
            return self.create_standardized_result(GT.CHILD_SUPPORT, record, error_message=f"{EM.ERROR_CALCULATING} child support: {e}")


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
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.FEDERAL_TAX_LEVY}
                ]
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = withholding_amount
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = CM.NA
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = CM.NA
            
            return result
            
        except Exception as e:
            self.logger.error(f"{EM.ERROR_CALCULATING} federal tax: {e}")
            return self.create_standardized_result(
                GT.FEDERAL_TAX_LEVY, record, error_message=f"{EM.ERROR_CALCULATING} federal tax: {e}")

    def calculate_student_loan(self, record, config_data=None, garn_fees=None):
        """
        Calculate student loan garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            override_amount = record.get('override_amount', 0)
            override_arrear = record.get('override_arrear', 0)
            override_limit = record.get('override_limit', 0)

            result = StudentLoanCalculator().calculate(record)
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(record)
            loan_amt = result[CRK.STUDENT_LOAN_AMT]

            if len(loan_amt) == 1:
                if isinstance(loan_amt, (int, float,list,dict)):
                    record[CR.AGENCY] = [{
                        CR.WITHHOLDING_AMT: [
                            {GT.STUDENT_DEFAULT_LOAN: loan_amt.values()}]}]
                else:
                    record[CR.AGENCY] = [{
                        CR.WITHHOLDING_AMT: [
                            {GT.STUDENT_DEFAULT_LOAN: loan_amt}]}]
            else:
                record[CR.AGENCY] = [{
                    CR.WITHHOLDING_AMT: [{GT.STUDENT_DEFAULT_LOAN: amt}
                                     for amt in loan_amt.values()]}]
            total_student_loan_amt = 0 if any(isinstance(
                val, str) for val in loan_amt.values()) else sum(loan_amt.values())
            record[CR.ER_DEDUCTION] = {CR.GARNISHMENT_FEES: self.fee_calculator.get_rounded_garnishment_fee(
                work_state, garnishment_type, pay_period, total_student_loan_amt, garn_fees)}
            record[CR.WITHHOLDING_BASIS] = CM.NA
            record[CR.WITHHOLDING_CAP] = CM.NA
            # Create standardized result
            standardized_result = self.create_standardized_result(GT.STUDENT_DEFAULT_LOAN, record)
            
            # Calculate total student loan amount
            total_student_loan_amt = 0
            withholding_amounts = []
            
            # Get garnishment data from input to extract case IDs
            garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
            student_loan_garnishment = None
            
            # Find student loan garnishment data
            for garnishment in garnishment_data:
                if garnishment.get(GDK.TYPE, '').lower() == GT.STUDENT_DEFAULT_LOAN:
                    student_loan_garnishment = garnishment
                    break
            
            if isinstance(loan_amt, dict):
                if student_loan_garnishment:
                    cases = student_loan_garnishment.get(GDK.DATA, [])
                    for idx, (key, amount) in enumerate(loan_amt.items()):
                        case_id = cases[idx].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{idx}") if idx < len(cases) else f"{GRF.CASE_PREFIX}{idx}"
                        
                        if isinstance(amount, (int, float)):
                            withholding_amounts.append({GRF.AMOUNT: round(amount, 2), GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_ID: case_id})
                            total_student_loan_amt += amount
                        else:
                            withholding_amounts.append({GRF.AMOUNT: GRF.INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_ID: case_id})
                else:
                    # Fallback to case_index if no garnishment data found
                    for idx, (key, amount) in enumerate(loan_amt.items()):
                        if isinstance(amount, (int, float)):
                            withholding_amounts.append({GRF.AMOUNT: round(amount, 2), GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_INDEX: idx})
                            total_student_loan_amt += amount
                        else:
                            withholding_amounts.append({GRF.AMOUNT: GRF.INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_INDEX: idx})
            elif isinstance(loan_amt, (int, float)):
                withholding_amounts.append({GRF.AMOUNT: round(loan_amt, 2), GRF.TYPE: GRF.STUDENT_LOAN})
                total_student_loan_amt = loan_amt
            else:
                withholding_amounts.append({GRF.AMOUNT: GRF.INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN})

            if total_student_loan_amt <= 0:
                standardized_result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                standardized_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
            else:
                garnishment_fees=self.fee_calculator.get_rounded_garnishment_fee(
                    work_state, garnishment_type, pay_period, total_student_loan_amt, garn_fees)
                garnishment_fees_amount = garnishment_fees
                
                standardized_result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = round(total_student_loan_amt, 2)
                standardized_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount

            standardized_result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
            standardized_result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(result[CRK.DISPOSABLE_EARNING], 2)
            standardized_result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            standardized_result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = CM.NA
            standardized_result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = CM.NA
            
            return standardized_result
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} student loan: {e}")
            return self.create_standardized_result(GT.STUDENT_DEFAULT_LOAN, record, error_message=f"{EM.ERROR_CALCULATING} student loan: {e}")

            
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
            data = garnishment_data[0].get(GDK.DATA, [])
            case_id = data[0].get("case_id") if data else None
            pay_period = record.get(EE.PAY_PERIOD, "")
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            override_amount = record.get('override_amount', 0)
            deduction_basis =record.get("deduction_basis",'NA')
            override_percent = record.get('override_percent', 0)
            gross_pay = record.get(EE.GROSS_PAY, 0)
            net_pay = record.get(EE.NET_PAY, 0)

            disposable_earning = self.calculate_de(record)

            if override_amount is not None and float(override_amount) > 0:
                calculation_result = UtilityClass.build_response(
                    override_amount, 0, CM.NA,
                    CM.NA,
                    {}
                )
            elif override_percent is not None and float(override_percent) > 0 and deduction_basis == 'NA':
                deduction_value = self.get_basis_map(gross_pay, net_pay, disposable_earning)
                calculation_result= UtilityClass.build_response(
                deduction_value * override_percent, disposable_earning,
                CM.NA, f"{override_percent * 100}% of {CM.DISPOSABLE_EARNING}",
                {"override_percent": override_percent,
                "override_percent_display": f"{override_percent*100}%"}
            )
            else:
                calculation_result = state_tax_view.calculate(record, config_data[GT.STATE_TAX_LEVY],override_percent)
            

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
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: EM.INSUFFICIENT_PAY, GRF.CASE_ID: case_id}
                ]
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result.get(CR.DISPOSABLE_EARNING, 0), 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = round(calculation_result[CR.WITHHOLDING_AMT], 2)
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.CASE_ID: case_id}
                ]
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})
                
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
            override_amount = record.get('override_amount', 0)
            override_percent = record.get('override_percent', 0)

            override_amount = record.get('override_amount', 0)
            deduction_basis =record.get("deduction_basis",'NA')
            override_percent = record.get('override_percent', 0)
            gross_pay = record.get(EE.GROSS_PAY, 0)
            net_pay = record.get(EE.NET_PAY, 0)

            disposable_earning = self.calculate_de(record)

            if override_amount is not None and float(override_amount) > 0:
                calculation_result = UtilityClass.build_response(
                    override_amount, 0, CM.NA,
                    CM.NA,
                    {}
                )
            elif override_percent is not None and float(override_percent) > 0 and deduction_basis is not 'NA':
                deduction_value = self.get_basis_map(gross_pay, net_pay, disposable_earning)
                calculation_result= UtilityClass.build_response(
                deduction_value * override_percent, disposable_earning,
                CM.NA, f"{override_percent * 100}% of {CM.DISPOSABLE_EARNING}",
                {"override_percent": override_percent,
                "override_percent_display": f"{override_percent*100}%"}
            )
            else:
                calculation_result = creditor_debt_calculator.calculate(record, config_data[GT.CREDITOR_DEBT])

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
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: EM.INSUFFICIENT_PAY, GRF.CASE_ID: case_id}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.CASE_ID: case_id}
                ]
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.CONDITION_VALUES] = calculation_result.get(GRF.CONDITION_VALUES, {})

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
            override_amount = record.get('override_amount', 0)
            override_percent = record.get('override_percent', 0)
            deduction_basis =record.get("deduction_basis",'NA')
            gross_pay = record.get(EE.GROSS_PAY, 0)
            net_pay = record.get(EE.NET_PAY, 0)

            disposable_earning = self.calculate_de(record)

            if override_amount is not None and float(override_amount) > 0:
                calculation_result = UtilityClass.build_response(
                    override_amount, 0, CM.NA,
                    CM.NA,
                    {}
                )
            elif override_percent is not None and float(override_percent) > 0 and deduction_basis is not 'NA':
                deduction_value = self.get_basis_map(gross_pay, net_pay, disposable_earning)
                calculation_result= UtilityClass.build_response(
                deduction_value * override_percent, disposable_earning,
                CM.NA, f"{override_percent * 100}% of {CM.DISPOSABLE_EARNING}",
                {"override_percent": override_percent,
                "override_percent_display": f"{override_percent*100}%"}
            )
            else:
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
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.BANKRUPTCY}
                ]
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
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
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
            override_amount = record.get('override_amount', 0)
            override_percent = record.get('override_percent', 0)

            deduction_basis =record.get("deduction_basis",'NA')
            gross_pay = record.get(EE.GROSS_PAY, 0)
            net_pay = record.get(EE.NET_PAY, 0)

            disposable_earning = self.calculate_de(record)

            if override_amount is not None and float(override_amount) > 0:
                calculation_result = UtilityClass.build_response(
                    override_amount, 0, CM.NA,
                    CM.NA,
                    {}
                )
            elif override_percent is not None and float(override_percent) > 0 and deduction_basis is not 'NA':
                deduction_value = self.get_basis_map(gross_pay, net_pay, disposable_earning)
                calculation_result= UtilityClass.build_response(
                deduction_value * override_percent, disposable_earning,
                CM.NA, f"{override_percent * 100}% of {CM.DISPOSABLE_EARNING}",
                {"override_percent": override_percent,
                "override_percent_display": f"{override_percent*100}%"}
            )
            else:
                calculation_result = FTB().calculate(record, config_data[garnishment_type])


            
            if not garnishment_data:
                return None
                
            garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "").strip().lower()

            # Check if the config exists for this type
            if garnishment_type not in config_data:
                self.logger.error(f"Config data for '{garnishment_type}' is missing. Available keys: {list(config_data.keys())}")
                return self.create_standardized_result(
                    garnishment_type, record,
                    error_message=f"{EM.CONFIG_DATA_MISSING} '{garnishment_type}' {EM.CONFIG_DATA_MISSING_END}")

            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            
            
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
                
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: garnishment_type}
                ]
                result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = withholding_amount
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
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
            result[GRF.GARNISHMENT_DETAILS][0][GRF.TOTAL_WITHHELD] = calculations.get('total_withholding_amount', 0.0)
            result[GRF.GARNISHMENT_DETAILS][0][GRF.NET_WITHHOLDING] = calculations.get('total_withholding_amount', 0.0)
            
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
            
            result[GRF.GARNISHMENT_DETAILS][0][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
            result[GRF.GARNISHMENT_DETAILS][0][GRF.ARREAR_AMOUNTS] = arrear_amounts
            
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

    def calculate_multiple_garnishment(self, record, config_data, garn_fees=None):
        """
        Calculate multiple garnishment with standardized result structure.
        """
        try:
            # Create standardized result for multiple garnishment
            result = self.create_standardized_result("multiple_garnishment", record)
            
            # Prepare record for multiple garnishment calculation
            # The MultipleGarnishmentPriorityOrder expects garnishment_orders to be in the record
            prepared_record = record.copy()
            prepared_record[GDK.GARNISHMENT_ORDERS] = record.get(GDK.GARNISHMENT_ORDERS, [])
            
            multiple_garnishment = MultipleGarnishmentPriorityOrder(prepared_record, config_data)

            
            work_state = record.get(EE.WORK_STATE)
            pay_period = record.get(EE.PAY_PERIOD, "")  
            calculation_result = multiple_garnishment.calculate()
            if calculation_result == CommonConstants.NOT_FOUND:
                result[GRF.CALCULATION_STATUS] = GRF.NOT_FOUND
                result[GRF.ERROR] = EM.NO_GARNISHMENT_CONFIGURATION
                return result
                
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                result[GRF.CALCULATION_STATUS] = GRF.NOT_PERMITTED
                result[GRF.ERROR] = EM.GARNISHMENT_NOT_PERMITTED_CASE
                return result
            
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(record.get(PT.PAYROLL_TAXES))
            total_withheld = 0.0
            
            # Process each garnishment type from the calculation results
            for garnishment_type, type_result in calculation_result.items():
                if isinstance(type_result, dict):
                    type_withholding_amounts = []
                    type_total_withheld = 0.0
                    
                    # Check if there's an error in this garnishment type calculation
                    calculation_status = type_result.get(GRF.CALCULATION_STATUS, "")
                    has_error_details = "error_details" in type_result
                    is_calculation_error = calculation_status == "calculation_error"
                    
                    # Extract error details if present
                    error_details = None
                    if has_error_details or is_calculation_error:
                        error_details = type_result.get("error_details", "")
                    
                    # Handle child support specific structure
                    if garnishment_type == GT.CHILD_SUPPORT:
                        result_amounts = type_result.get(CRK.RESULT_AMT, {})
                        arrear_amounts = type_result.get(CRK.ARREAR_AMT, {})
                        
                        # Initialize separate lists for withholding and arrear amounts
                        type_arrear_amounts = []
                        
                        # Get garnishment data from input to extract case IDs
                        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                        child_support_garnishment = None
                        
                        # Find child support garnishment data
                        for garnishment in garnishment_data:
                            if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                                child_support_garnishment = garnishment
                                break
                        
                        if child_support_garnishment:
                            cases = child_support_garnishment.get(GDK.DATA, [])
                            result_amounts_list = list(result_amounts.values())
                            arrear_amounts_list = list(arrear_amounts.values())
                            total_withheld_amount = sum(result_amounts_list) + sum(arrear_amounts_list)
                            
                            # Add current support amounts to withholding_amounts
                            for i, (key, amount) in enumerate(result_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.CURRENT_SUPPORT,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                            
                            # Add arrear amounts to separate arrear_amounts list
                            for i, (key, amount) in enumerate(arrear_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_arrear_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.ARREAR,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                        else:
                            # Fallback to case_index if no garnishment data found
                            for i, (key, amount) in enumerate(result_amounts.items()):
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.CURRENT_SUPPORT,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                            
                            for i, (key, amount) in enumerate(arrear_amounts.items()):
                                type_arrear_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.ARREAR,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                    
                    # Add child support result with error details if present
                    if garnishment_type == GT.CHILD_SUPPORT:
                        garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                        work_state, garnishment_type, pay_period, total_withheld_amount)
                        child_support_result = {
                            GRF.GARNISHMENT_TYPE: garnishment_type,
                            GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                            GRF.ARREAR_AMOUNTS: type_arrear_amounts,
                            GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                            GRF.NET_WITHHOLDING: round(type_total_withheld),
                            GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                            GRF.GARNISHMENT_FEES : garnishment_fees_amount,
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0),
                            GRF.WITHHOLDING_BASIS: CM.NA,
                            GRF.WITHHOLDING_CAP: CM.NA,
                            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                            GRF.CONDITION_VALUES: {}
                        }
                        
                        # Add error details if present
                        if error_details is not None:
                            child_support_result["error_details"] = error_details
                            
                        result[GRF.GARNISHMENT_DETAILS].append(child_support_result)
                        total_withheld += type_total_withheld
                        continue
                    
                    # Handle student loan specific structure
                    elif garnishment_type == GT.STUDENT_DEFAULT_LOAN:
                        student_loan_amounts = type_result.get(CRK.STUDENT_LOAN_AMT, {})
                        
                        # Get garnishment data from input to extract case IDs
                        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                        student_loan_garnishment = None
                        
                        # Find student loan garnishment data
                        for garnishment in garnishment_data:
                            if garnishment.get(GDK.TYPE, '').lower() == GT.STUDENT_DEFAULT_LOAN:
                                student_loan_garnishment = garnishment
                                break
                        
                        if student_loan_garnishment:
                            cases = student_loan_garnishment.get(GDK.DATA, [])
                            for i, (key, amount) in enumerate(student_loan_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.STUDENT_LOAN,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                        else:
                            # Fallback to case_index if no garnishment data found
                            for i, (key, amount) in enumerate(student_loan_amounts.items()):
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.STUDENT_LOAN,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                    
                    # Add student loan result with error details if present
                    elif garnishment_type == GT.STUDENT_DEFAULT_LOAN:
                        garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                    work_state, garnishment_type, pay_period, type_total_withheld)
                        
                        student_loan_result = {
                            GRF.GARNISHMENT_TYPE: garnishment_type,
                            GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                            GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                            GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                            GRF.GARNISHMENT_FEES : garnishment_fees_amount,
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0),
                            GRF.WITHHOLDING_BASIS: CM.NA,
                            GRF.WITHHOLDING_CAP: CM.NA,
                            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                            GRF.CONDITION_VALUES: {}
                        }
                        
                        # Add error details if present
                        if error_details is not None:
                            student_loan_result["error_details"] = error_details
                            
                        result[GRF.GARNISHMENT_DETAILS].append(student_loan_result)
                        total_withheld += type_total_withheld
                        continue
                    
                    # Handle spousal_and_medical_support with detailed priority information
                    elif garnishment_type == GT.SPOUSAL_AND_MEDICAL_SUPPORT:
                        # Preserve all the detailed calculation information
                        withholding_amount = type_result.get(CR.WITHHOLDING_AMT, 0)
                        
                        # Extract case_id from garnishment_data
                        case_id = self._extract_case_id_from_garnishment_data(record, garnishment_type)
                        
                        type_withholding_amounts.append({
                            GRF.AMOUNT: round(withholding_amount, 2),
                            GRF.CASE_ID: case_id
                        })
                        type_total_withheld = withholding_amount
                        garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                    work_state, garnishment_type, pay_period, type_total_withheld)
                        
                        # Add detailed calculation information to the result
                        detailed_result = {
                            GRF.GARNISHMENT_TYPE: garnishment_type,
                            GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                            GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                            GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                            GRF.GARNISHMENT_FEES : garnishment_fees_amount,
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0),
                            GRF.WITHHOLDING_BASIS: CM.NA,
                            GRF.WITHHOLDING_CAP: CM.NA,
                            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                            GRF.CONDITION_VALUES: {},

                            # Preserve all detailed calculation information
                            "success": type_result.get("success", True),
                            "calculations": type_result.get("calculations", {}),
                            "deduction_details": type_result.get("deduction_details", []),
                            "summary": type_result.get("summary", {})
                            
                        }
                        
                        # Add error details if present
                        if error_details is not None:
                            detailed_result["error_details"] = error_details
                        
                        # Add garnishment type to result with detailed information
                        result[GRF.GARNISHMENT_DETAILS].append(detailed_result)
                        total_withheld += type_total_withheld
                        continue  # Skip the generic processing below
                    
                    # Handle other garnishment types (creditor debt, etc.)
                    else:
                        withholding_amount = type_result.get(CR.WITHHOLDING_AMT, 0)
                        withholding_basis =type_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                        withholding_cap =type_result.get(CR.WITHHOLDING_CAP, CM.NA)
                        
                        
                        # Extract case_id from garnishment_data
                        case_id = self._extract_case_id_from_garnishment_data(record, garnishment_type)
                        
                        type_withholding_amounts.append({
                            GRF.AMOUNT: round(withholding_amount, 2),
                            GRF.CASE_ID: case_id
                        })
                        type_total_withheld = withholding_amount
                        type_withholding_basis = withholding_basis
                        type_withholding_cap = withholding_cap


                    if garnishment_type in [GRF.CREDITOR_DEBT, GRF.STATE_TAX_LEVY]:
                        garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                    work_state, garnishment_type, pay_period, withholding_amount)
                        
                        garnishment_result = {
                            GRF.GARNISHMENT_TYPE: garnishment_type,
                            GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                            GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                            GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                            GRF.WITHHOLDING_BASIS: type_withholding_basis,
                            GRF.WITHHOLDING_CAP: type_withholding_cap,
                            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                            GRF.CONDITION_VALUES: type_result.get(GRF.CONDITION_VALUES, {}),
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0),
                            GRF.GARNISHMENT_FEES: garnishment_fees_amount
                        }
                        
                        # Add error details if present
                        if error_details is not None:
                            garnishment_result["error_details"] = error_details
                            
                        result[GRF.GARNISHMENT_DETAILS].append(garnishment_result)

                    else:
                        garnishment_fees_amount = self.fee_calculator.get_rounded_garnishment_fee(
                    work_state, garnishment_type, pay_period, type_total_withheld)
                    
                        # Add garnishment type to result
                        garnishment_result = {
                            GRF.GARNISHMENT_TYPE: garnishment_type,
                            GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                            GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                            GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0),
                            GRF.GARNISHMENT_FEES: garnishment_fees_amount,
                            GRF.WITHHOLDING_BASIS: CM.NA,
                            GRF.WITHHOLDING_CAP: CM.NA,
                            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                            GRF.CONDITION_VALUES: {}
                        }
                        
                        # Add error details if present
                        if error_details is not None:
                            garnishment_result["error_details"] = error_details
                            
                        result[GRF.GARNISHMENT_DETAILS].append(garnishment_result)
                        
                    
                    total_withheld += type_total_withheld
                    
            # Calculate garnishment fees
            garnishment_fees_amount = 0.0
                # Calculate garnishment fees
            # garnishment_fees_amount = self.get_rounded_garnishment_fee(
            #         work_state, record, calculation_result[CR.WITHHOLDING_AMT])
            
            # Note: Aggregate totals are not stored in GARNISHMENT_DETAILS list
            # Each item in the list already contains its own TOTAL_WITHHELD, GARNISHMENT_FEES, etc.
            
            # Update calculation metrics
            if GT.CHILD_SUPPORT in calculation_result:
                child_support_result = calculation_result[GT.CHILD_SUPPORT]
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(child_support_result.get(CRK.ADE, 0), 2)
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CRK.DISPOSABLE_EARNING], 2)
            elif GT.SPOUSAL_AND_MEDICAL_SUPPORT in calculation_result:
                spousal_and_medical_support_result = calculation_result[GT.SPOUSAL_AND_MEDICAL_SUPPORT]
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CRK.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(spousal_and_medical_support_result["calculations"].get('allowable_disposable_earnings', 0), 2)
            
            result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            result[GRF.CALCULATION_METRICS][CRK.TWENTY_FIVE_PERCENT_OF_DE] = round(calculation_result[CRK.TWENTY_FIVE_PERCENT_OF_DE], 2)

            # Update employer deductions
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")
            return self.create_standardized_result("multiple_garnishment", record, error_message=f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")
                

    def create_standardized_result(self, garnishment_type: str, record: Dict, 
                                 calculation_result: Dict = None, error_message: str = None) -> Dict:
        """
        Creates a standardized result structure for garnishment calculations.
        This ensures consistency across all garnishment types.
        For multiple garnishments, creates an empty list. For single garnishments, creates a list with one item.
        """
        # For multiple garnishments, create an empty list. For single garnishments, create a list with one item.
        is_multiple = garnishment_type == "multiple_garnishment"
        
        garnishment_details = [] if is_multiple else [{
            GRF.GARNISHMENT_TYPE: garnishment_type,
            GRF.WITHHOLDING_AMOUNTS: [],
            GRF.ARREAR_AMOUNTS: [],
            GRF.TOTAL_WITHHELD: 0.0,
            GRF.NET_WITHHOLDING: 0.0,
            GRF.WITHHOLDING_BASIS: CM.NA,
            GRF.WITHHOLDING_CAP: CM.NA,
            GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
            GRF.CONDITION_VALUES: {}
        }]
        
        result = {
            GRF.EMPLOYEE_ID: record.get(EE.EMPLOYEE_ID),
            GRF.WORK_STATE: record.get(EE.WORK_STATE),
            GRF.IS_MULTIPLE_GARNISHMENT_TYPE:record.get(GRF.IS_MULTIPLE_GARNISHMENT_TYPE),
            GRF.CALCULATION_STATUS: GRF.SUCCESS if not error_message else GRF.ERROR,
            GRF.GARNISHMENT_DETAILS: garnishment_details,
            GRF.CALCULATION_METRICS: {
                GRF.DISPOSABLE_EARNINGS: 0.0,
                GRF.TOTAL_MANDATORY_DEDUCTIONS: 0.0,
                GRF.ALLOWABLE_DISPOSABLE_EARNINGS: 0.0
            },
            CR.ER_DEDUCTION: {
                GRF.GARNISHMENT_FEES: 0.0
            }
        }
        
        if error_message:
            result[GRF.ERROR] = error_message
            result[GRF.CALCULATION_STATUS] = GRF.ERROR
            
        return result
