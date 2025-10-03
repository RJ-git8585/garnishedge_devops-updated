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
import logging
import traceback as t

class FTBStateTaxLevyFormulas():
    """
    State-specific formulas for FTB state tax levy calculations.

    """
# (config_data, state, pay_period,garn_start_date,garnishment_type, is_consumer_debt=None, non_consumer_debt=None)

    def _exempt_amt_config_data(self,config_data, state, pay_period,garn_start_date,garnishment_type, is_consumer_debt=None, non_consumer_debt=None):
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
                         and (i.get("garnishment_type" ) == garnishment_type or i.get("garnishment_type" ) is None)
                     ),
                     None
                 )        
         except Exception as e:
             return Response(
             {
                 "error": f"Exception in CreditorDebtCalculator.calculate: {str(e)}"
             }
         )
    def cal_california(self,garnishment_types, config_data, disposable_earning):
        try:
            if garnishment_types.lower() == "ftb_ewot".lower():
                return CreditorDebtHelper()._general_debt_logic(disposable_earning, config_data)
            elif garnishment_types.lower() in ["ftb_court","ftb_vehicle"]:
                return CreditorDebtHelper()._general_ftb_debt_logic(disposable_earning, config_data)
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _general_ftb_debt_logic: {str(e)}"
            )
              
class FTB(FTBStateTaxLevyFormulas):
    def calculate(self, record, config_data):
        """
        Main entry point for creditor debt calculation.
        Determines the state and applies the appropriate formula.
        """
        try: 
            gross_pay = record.get(EE.GROSS_PAY)
            state = StateAbbreviations(record.get(
                EE.WORK_STATE)).get_state_name_and_abbr()
            wages = record.get(CF.WAGES, 0)
            garnishment_data = record.get("garnishment_data")
            if not garnishment_data:
                return None
            garnishment_type = garnishment_data[0].get(
                    EE.GARNISHMENT_TYPE, "").strip().lower()
            garn_start_date=record.get(EE.GARN_START_DATE)
            pay_period = record.get(EE.PAY_PERIOD).lower()
            cs_helper=ChildSupportHelper(state)
            commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
            disposable_earning = cs_helper.calculate_de(gross_pay, mandatory_deductions)
            config_data=self._exempt_amt_config_data(config_data, state, pay_period,garn_start_date,garnishment_type, is_consumer_debt=None, non_consumer_debt=None)
            return self.cal_california(garnishment_type, config_data, disposable_earning)
            

        except Exception as e:
            return Response(
                {
                    "error": f"Exception in calculating ftb for California: {e} "
                }
            )
        
        