from processor.garnishment_library.calculations.creditor_debt import CreditorDebtHelper, UtilityClass
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
from rest_framework.response import Response
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
    def cal_california(self, ftb_type, config_data, disposable_earning):
        try:
            if ftb_type.lower() == GT.STATE_TAX_LEVY.lower():
                return CreditorDebtHelper()._general_debt_logic(disposable_earning, config_data)
            else:
                return CreditorDebtHelper()._general_ftb_debt_logic(disposable_earning, config_data)
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _general_ftb_debt_logic: {str(e)}"
            )
              
class FranchaiseTaxBoard(StateWiseFTBStateTaxLevyFormulas):
    def calculate(self, record, config_data):
        """
        Main entry point for creditor debt calculation.
        Determines the state and applies the appropriate formula.
        """
        try: 
            gross_pay = record.get(EE.GROSS_PAY)
            ftb_type= record.get('ftb_type')
            state = StateAbbreviations(record.get(
                EE.WORK_STATE)).get_state_name_and_abbr()
            wages = record.get(CF.WAGES, 0)
            garn_start_date=record.get(EE.GARN_START_DATE)
            pay_period = record.get(EE.PAY_PERIOD).lower()
            cs_helper=ChildSupportHelper(state)
            commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
            disposable_earning = cs_helper.calculate_de(gross_pay, mandatory_deductions)
            config_data=self._exempt_amt_config_data(config_data, state, pay_period,garn_start_date,ftb_type, is_consumer_debt=None, non_consumer_debt=None)
            return self.cal_california(ftb_type, config_data, disposable_earning)
            
        except Exception as e:
            import traceback as t
            print(t.print_exc())
            return Response(
                {
                    "error": f"Exception in calculating ftb for California: {e} "
                }
            )
        
        