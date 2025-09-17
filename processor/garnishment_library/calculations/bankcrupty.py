from processor.garnishment_library.utils.response import UtilityClass, CalculationResponse as CR
from rest_framework.response import Response
from user_app.constants import (
    StateList as ST,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    CalculationMessages as CM,
    ExemptConfigFields as EC,
    CalculationResponseFields as CRF,
    CommonConstants as CC,
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    FilingStatusFields
)
from processor.garnishment_library.utils import StateAbbreviations
from processor.garnishment_library.calculations import ChildSupportHelper
from processor.garnishment_library.calculations import CreditorDebtHelper
from rest_framework import status

class StateWiseFTBStateTaxLevyFormulas():
    """
    State-specific formulas for FTB state tax levy calculations.

    """


    def _exempt_amt_config_data(self,config_data, state, pay_period,garn_start_date,ftb_type, is_consumer_debt=None, non_consumer_debt=None):
         """
         Helper to fetch the correct config for the state, pay period, and optionally debt type.
         """
         debt_type = None
         if is_consumer_debt:
             debt_type = "consumer"
         elif non_consumer_debt:
             debt_type = "non consumer"
         garn_start_date =CreditorDebtHelper()._gar_start_date_check(garn_start_date)
         try:
             return next(
                     ( i for i in config_data
                         if i[EE.STATE].lower() == state.lower()
                         and i[EE.PAY_PERIOD].lower() == pay_period.lower()
                         and (i.get("debt_type") is None or i.get("debt_type").lower() == debt_type or not i.get("debt_type")) 
                         and (i.get("start_gt_5dec24") is None or i.get("start_gt_5dec24") == garn_start_date)
                         and i.get("ftb_type" ) == ftb_type
                     ),
                     None
                 )        
         except Exception as e:
             return Response(
             {
                 "error": f"Exception in CreditorDebtCalculator.calculate: {str(e)}"
             }
         )

class Bankruptcy(StateWiseFTBStateTaxLevyFormulas):
    """
    Handles calculation for bankruptcy garnishment.

    """
    def calculate(self, record, config_data):
        try:
            CSH=ChildSupportHelper()
            # Extract required values from record
            bankruptcy_amount = record.get(GT.BANKRUPTCY_AMOUNT, 0)
            child_support_amount = record.get(GT.CHILD_SUPPORT_AMOUNT, 0)
            spousal_support_amount = record.get(GT.SPOUSAL_SUPPORT_AMOUNT, 0)
            wages = record.get(CF.WAGES, 0)
            commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PT.PAYROLL_TAXES)

            gross_pay = CSH.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = CSH.calculate_md(payroll_taxes)
            de = CSH.calculate_de(gross_pay, mandatory_deductions)

            allowable_bankruptcy_amount = de - (child_support_amount + spousal_support_amount)
            if allowable_bankruptcy_amount < 0:
                allowable_bankruptcy_amount = 0

            available_for_bankruptcy = 0.25 * allowable_bankruptcy_amount
            federal_min_wage_threshold = self._exempt_amt_config_data()

            if available_for_bankruptcy <= federal_min_wage_threshold:
                withholding_amount = 0
                return UtilityClass.build_response(
                    0, de, CM.DE_BANKRUPTCY_LE_LOWER, CR.get_zero_withholding_response(available_for_bankruptcy, CM.LOWER_THRESHOLD_AMOUNT))
            else:
                withholding_amount = min(available_for_bankruptcy, bankruptcy_amount)
                return UtilityClass.build_response(
                    withholding_amount, de, CM.DE_BANKRUPTCY_LE_UPPER, f"Min({available_for_bankruptcy}, {bankruptcy_amount})")

        except Exception as e:
            raise ValueError(f"Error in Bankruptcy calculation: {str(e)}")

