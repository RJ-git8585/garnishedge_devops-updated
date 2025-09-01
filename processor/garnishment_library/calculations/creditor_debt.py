from rest_framework.response import Response
from rest_framework import status
from .child_support import *
from processor.garnishment_library.utils import *
from processor.garnishment_library.utils.response import UtilityClass, CalculationResponse as CR
from user_app.constants import (
    StateList as ST,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    CalculationMessages as CM,
    ExemptConfigFields as EC,
    FilingStatusFields as FS,
    CommonConstants as CC,
    CalculationResponseFields as CRF,
)
from datetime import datetime
import traceback as t

class CreditorDebtHelper():
    """
    Helper class for general creditor debt logic.

    """

    
    def _gar_start_date_check(self,garn_start_date):

        date = datetime(2022, 12, 5).date()
        
        garn_start_date = garn_start_date.replace("-", "/")
        filed_date = datetime.strptime(garn_start_date, "%m/%d/%Y").date()
        if filed_date > date :
            return True
        elif filed_date < date:
            return False
        
    def _exempt_amt_config_data(self,config_data, state, pay_period,garn_start_date, is_consumer_debt=None, non_consumer_debt=None,home_state=None):
            """
            Helper to fetch the correct config for the state, pay period, and optionally debt type.
            """

            debt_type = None
            if is_consumer_debt:
                debt_type = "consumer"
            elif non_consumer_debt:
                debt_type = "non consumer"
            garn_start_date =self._gar_start_date_check(garn_start_date)
            try:
                return next(
                        ( i for i in config_data
                            if i[EmployeeFields.STATE].lower() == state.lower()
                            and i[EmployeeFields.PAY_PERIOD].lower() == pay_period.lower()
                            and (i.get("debt_type") is None or i.get("debt_type").lower() == debt_type or not i.get("debt_type")) 
                            and (i.get("start_gt_5dec24") is None or i.get("start_gt_5dec24") == garn_start_date)
                            and (i.get("home_state") is None or i.get("home_state").lower() == home_state.lower())
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

    def _general_debt_logic(self, disposable_earning, config_data):
        """
        Calculate the amount of disposable earnings that can be garnished for creditor debt
        using the general formula (used by multiple states).
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            upper_threshold_percent = float(
                config_data[EC.UPPER_THRESHOLD_PERCENT])/100
            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
            elif lower_threshold_amount <= disposable_earning <= upper_threshold_amount:
                return UtilityClass.build_response(disposable_earning - lower_threshold_amount, disposable_earning,
                                                CM.DE_GT_LOWER_LT_UPPER, f"{CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT}")
            elif disposable_earning >= upper_threshold_amount:
                return UtilityClass.build_response(
                    upper_threshold_percent * disposable_earning, disposable_earning, CM.DE_GT_UPPER, f"{upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _general_debt_logic: {str(e)}"
            )

    def _minimum_wage_threshold_compare(self, disposable_earning, config_data):
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            lower_threshold_percent = float(
                config_data[EC.LOWER_THRESHOLD_PERCENT1])/100

            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
            elif disposable_earning > lower_threshold_amount:
                diff_of_de_and_threshold_amount = disposable_earning - lower_threshold_amount
                de_percent = disposable_earning * lower_threshold_percent
                return UtilityClass.build_response(
                    min(diff_of_de_and_threshold_amount,
                        de_percent), disposable_earning, CM.DE_GT_UPPER,
                    f"Min({lower_threshold_percent * 100}% of {CM.DISPOSABLE_EARNING}, ({CM.DISPOSABLE_EARNING} - threshold_amount))"
                )
        except Exception as e:

            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _minimum_wage_threshold_compare: {str(e)}"
            )
        
    def _general_ftb_debt_logic(self, disposable_earning, config_data):
        """
        Calculate the amount of disposable earnings that can be garnished for creditor debt
        using the general formula (used by multiple states).
        """
        try:
            print("config_data", config_data)
            lower_threshold_amount =float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            upper_threshold_percent = float(
                config_data[EC.UPPER_THRESHOLD_PERCENT]) / 100
            de_range_lower_to_upper_threshold_percent = float(
                config_data[EC.DE_RANGE_LOWER_TO_UPPER_THRESHOLD_PERCENT]) / 100
            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
            elif lower_threshold_amount < disposable_earning <= upper_threshold_amount:
                withholding_amount = (disposable_earning - lower_threshold_amount) * de_range_lower_to_upper_threshold_percent
                return UtilityClass.build_response(withholding_amount, disposable_earning,
                                                    CM.DE_GT_LOWER_LT_UPPER, f"({CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT}) * {de_range_lower_to_upper_threshold_percent*100}%")
            elif disposable_earning > upper_threshold_amount:
                withholding_amount = upper_threshold_percent * disposable_earning
                return UtilityClass.build_response(withholding_amount, disposable_earning, CM.DE_GT_UPPER, f"{upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")
        except Exception as e:
            import traceback as t
            t.print_exc()

            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _general_debt_logic: {str(e)}"
            )

class StateWiseCreditorDebtFormulas(CreditorDebtHelper):
    """
    Contains state-specific creditor debt calculation formulas.
    Each method implements the logic for a particular state.
    
    """

    def cal_alaska(self,home_state, disposable_earning, config_data):
        if home_state == ST.ALASKA.lower():
            return self._general_debt_logic(self, disposable_earning, config_data)
        elif home_state != ST.ALASKA.lower():
            return self._minimum_wage_threshold_compare(self, disposable_earning, config_data)
        return UtilityClass.build_response(
                0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
     

    def cal_delaware(self, disposable_earning, config_data):
        """
        Delaware: Garnishment calculation based on deducted basis percent.
        """
        try:
            PERCENT_LIMIT = float(
                config_data[EC.PERCENT_LIMIT]) / 100
            withholding_amt = disposable_earning * PERCENT_LIMIT

            return UtilityClass.build_response(
                withholding_amt, disposable_earning, "NA",
                f"{PERCENT_LIMIT*100}% of {CM.DISPOSABLE_EARNING}"
            )
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_delaware: {str(e)}"
            )

    def cal_hawaii(self, disposable_earning, config_data):
        """
        Hawaii: Garnishment calculation based on weekly to monthly conversion.
        """

        try:
            # calculating the disposable earning for monthly basis
            mde = disposable_earning*52/12

            if disposable_earning >= 200:
                de_five_percent = 0.05*100
                de_ten_percent = 0.10*100
                rmde = mde-200
                de_twenty_percent = 0.20*rmde
                mde_total = de_five_percent+de_ten_percent+de_twenty_percent
                wa = mde_total*12/52

                general_debt_logic = self._general_debt_logic(
                    disposable_earning, config_data)

                withholding_amt = general_debt_logic[CRF.WITHHOLDING_AMT]
                withholding_cap = general_debt_logic[CRF.WITHHOLDING_CAP]

                lesser_amt = min(wa, withholding_amt)
                return UtilityClass.build_response(lesser_amt, disposable_earning,
                                                   f"{CM.DISPOSABLE_EARNING} >= 200",
                                                   f"Min({CM.WITHHOLDING_AMT},{withholding_cap})")
            else:
                return UtilityClass.build_response(0, disposable_earning,
                                                   "de < 200",
                                                   CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_hawaii: {str(e)}"
            )

    def cal_new_jersey(self, gross_pay, config_data):
        """
        New Jersey: Garnishment calculation based on deducted basis percent of gross pay.
        """
        try:
            PERCENT_LIMIT = float(
                config_data[EC.PERCENT_LIMIT]) / 100
            return UtilityClass.build_response(
                gross_pay * PERCENT_LIMIT, 0, "NA",
                f"{PERCENT_LIMIT*100}% of gross pay"
            )
        except Exception as e:
            return UtilityClass.build_response(
                0, 0, "ERROR",
                f"Exception in cal_new_jersey: {str(e)}"
            )

    def cal_maine(self, disposable_earning, config_data):
        """
        Maine: Garnishment calculation with lower and upper thresholds.
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            upper_threshold_percent = float(
                config_data[EC.UPPER_THRESHOLD_PERCENT]) / 100

            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CR.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                )
            elif lower_threshold_amount <= disposable_earning <= upper_threshold_amount:
                diff = disposable_earning - lower_threshold_amount
                return UtilityClass.build_response(
                    diff, disposable_earning, CM.DE_GT_LOWER_LT_UPPER,
                    f"{CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT}"
                )
            elif disposable_earning >= upper_threshold_amount:
                return UtilityClass.build_response(
                    disposable_earning * upper_threshold_percent, disposable_earning,
                    CM.DE_GT_UPPER, f"{upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}"
                )
            else:
                return UtilityClass.build_response(
                    0, disposable_earning, "ERROR",
                    "Unhandled case in cal_maine"
                )
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_maine: {str(e)}"
            )
        

    def cal_missouri(self, disposable_earning, filing_status, config_data):
        """
        Missouri: Garnishment calculation based on filing status.
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            filing_status_percent = float(
                config_data[EC.FILING_STATUS_PERCENT]) / 100

            if filing_status == FS.HEAD_OF_HOUSEHOLD:
                if disposable_earning <= lower_threshold_amount:
                    return UtilityClass.build_response(0, disposable_earning,
                                                       CM.DE_LE_LOWER,
                                                       CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
                elif lower_threshold_amount <= disposable_earning <= upper_threshold_amount:
                    return UtilityClass.build_response(upper_threshold_amount - disposable_earning, disposable_earning,
                                                       CM.DE_GT_LOWER_LT_UPPER,
                                                       f"{CM.DISPOSABLE_EARNING} - {CM.UPPER_THRESHOLD_AMOUNT}")
                elif disposable_earning >= upper_threshold_amount:
                    return UtilityClass.build_response(filing_status_percent * disposable_earning, disposable_earning,
                                                       CM.DE_GT_UPPER,
                                                       f"{filing_status_percent * 100}% of {CM.DISPOSABLE_EARNING}")
            else:
                withholding_amt = self._general_debt_logic(
                    disposable_earning, config_data)
                return UtilityClass.build_response(withholding_amt[CRF.WITHHOLDING_AMT], disposable_earning, withholding_amt[CRF.WITHHOLDING_BASIS], withholding_amt[CRF.WITHHOLDING_CAP])

        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_missouri: {str(e)}"
            )

    def cal_nebraska(self, disposable_earning, filing_status, config_data):
        """
        Nebraska: Garnishment calculation based on filing status.
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            filing_status_percent = float(
                config_data[EC.FILING_STATUS_PERCENT]) / 100

            if filing_status == FS.HEAD_OF_HOUSEHOLD:
                if disposable_earning <= lower_threshold_amount:
                    withholding_amt = UtilityClass.build_response(
                        0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))

                elif lower_threshold_amount <= disposable_earning <= upper_threshold_amount:
                    withholding_amt = UtilityClass.build_response(disposable_earning-lower_threshold_amount, disposable_earning,
                                                                  CM.DE_GT_LOWER_LT_UPPER, f"{CM.UPPER_THRESHOLD_AMOUNT} - {CM.DISPOSABLE_EARNING}")
                elif disposable_earning >= upper_threshold_amount:
                    withholding_amt = UtilityClass.build_response(
                        filing_status_percent * disposable_earning, disposable_earning, CM.DE_GT_UPPER, f"{filing_status_percent * 100}% of {CM.DISPOSABLE_EARNING}")
                return withholding_amt
            else:
                withholding_amt = self._general_debt_logic(
                    disposable_earning, config_data)
                return UtilityClass.build_response(withholding_amt[CRF.WITHHOLDING_AMT], disposable_earning, withholding_amt[CRF.WITHHOLDING_BASIS], withholding_amt[CRF.WITHHOLDING_CAP])

        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_nebraska: {str(e)}"
            )

    def cal_north_dakota(self, disposable_earning, no_of_exemption_including_self, config_data):
        """
        North Dakota: Garnishment calculation based on exemption count.
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            exempt_amt = float(config_data[EC.EXEMPT_AMOUNT])
            lower_threshold_percent = float(
                config_data[EC.LOWER_THRESHOLD_PERCENT1]) / 100

            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))

            else:  # disposable_earning > lower_threshold_amount
                if no_of_exemption_including_self == 0:
                    diff_of_de_and_lower_threshold_amount = disposable_earning-lower_threshold_amount
                    de_percent = disposable_earning*lower_threshold_percent
                    return UtilityClass.build_response(
                        min(diff_of_de_and_lower_threshold_amount, de_percent), disposable_earning, CM.DE_GT_LOWER, f"Min({lower_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}, {CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT})")
                elif no_of_exemption_including_self >= 1:
                    diff_of_de_and_lower_threshold_amount = disposable_earning-lower_threshold_amount
                    de_percent = disposable_earning*lower_threshold_percent
                    min_amt =(min(diff_of_de_and_lower_threshold_amount, de_percent))
                    dependent_exemption = exempt_amt * \
                        no_of_exemption_including_self
                    if min_amt <= dependent_exemption:
                        return UtilityClass.build_response(
                            0, disposable_earning, CM.DE_GT_LOWER,
                            CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                        )
                    else:
                        return UtilityClass.build_response(
                                min_amt-dependent_exemption, disposable_earning, CM.DE_GT_LOWER, f"Min({lower_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}, {CM.DISPOSABLE_EARNING} - ({CM.LOWER_THRESHOLD_AMOUNT} + ({CM.LOWER_THRESHOLD_AMOUNT}+dependent_exemption)))")

        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_north_dakota: {str(e)}"
            )

    def cal_tennessee(self, disposable_earning, no_of_dependent_child, config_data):
        """
        washington: Garnishment calculation based on disposable_earning and no_of_dependent_child.
        """
        try:

            exempt_amt = float(config_data[EC.EXEMPT_AMOUNT])
            general_result = self._general_debt_logic(
                disposable_earning, config_data)
            if no_of_dependent_child == 0:
                return UtilityClass.build_response(general_result[CRF.WITHHOLDING_AMT], disposable_earning,
                                                   general_result[CRF.WITHHOLDING_BASIS], f"{general_result[CRF.WITHHOLDING_CAP]}")
            else:
                exempt_amt_for_dependent = exempt_amt*no_of_dependent_child
                withholding_amt = general_result[CRF.WITHHOLDING_AMT] - \
                    exempt_amt_for_dependent
                return UtilityClass.build_response(withholding_amt, disposable_earning,
                                                   general_result[CRF.WITHHOLDING_BASIS], f"{general_result[CRF.WITHHOLDING_CAP]}-Exempt Amount for Dependent")
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_tennessee: {str(e)}"
            )

    def cal_nevada(self, gross_pay, disposable_earning, config_data, percent1=.18):
        """
        Nevada: Garnishment calculation based on lower threshold and percent.
        """
        try:
            wl_limit_threshold = 770
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            lower_threshold_percent = float(
                config_data[EC.LOWER_THRESHOLD_PERCENT1]) / 100

            if gross_pay <= wl_limit_threshold:
                withholding_amt = disposable_earning*percent1
                return UtilityClass.build_response(withholding_amt, disposable_earning,
                                                   f"{CM.GROSS_PAY} <= {wl_limit_threshold}", f"{percent1*100}% of {CM.DISPOSABLE_EARNING}")
            else:  # disposable_earning > lower_threshold_amount
                diff_of_de_and_fmw_fifty_times = disposable_earning-lower_threshold_amount
                twenty_five_percent_of_de = disposable_earning*lower_threshold_percent
                withholding_amt = min(
                    diff_of_de_and_fmw_fifty_times, twenty_five_percent_of_de)
                return UtilityClass.build_response(withholding_amt, disposable_earning,
                                                   CM.DE_GT_LOWER,
                                                   f"Min(({CM.DISPOSABLE_EARNING}-{CM.LOWER_THRESHOLD_AMOUNT}),{lower_threshold_percent*100}% of {CM.DISPOSABLE_EARNING})")
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_nevada: {str(e)}"
            )

    def cal_minnesota(self, disposable_earning, config_data):
        """
        Minnesota: Garnishment calculation based on lower threshold and percent,mid threshold and percent,upper threshold and percent.
        """
        try:
            lower_threshold_amount = float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            mid_threshold_amount = float(
                config_data[EC.MID_THRESHOLD_AMOUNT])
            de_range_lower_to_mid_threshold_percent = float(
                config_data[EC.DE_RANGE_LOWER_TO_MID_THRESHOLD_PERCENT]) / 100
            de_range_mid_to_upper_threshold_percent = float(
                config_data[EC.DE_RANGE_MID_TO_UPPER_THRESHOLD_PERCENT]) / 100
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            upper_threshold_percent = float(
                config_data[EC.UPPER_THRESHOLD_PERCENT]) / 100
            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
            elif disposable_earning >= lower_threshold_amount and disposable_earning <= mid_threshold_amount:
                return UtilityClass.build_response(
                    de_range_lower_to_mid_threshold_percent*disposable_earning, disposable_earning, f"{CM.DISPOSABLE_EARNING} > {CM.LOWER_THRESHOLD_AMOUNT} and {CM.DISPOSABLE_EARNING} <= {CM.MID_THRESHOLD_AMOUNT}", f"{de_range_lower_to_mid_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")
            elif disposable_earning >= mid_threshold_amount and disposable_earning <= upper_threshold_amount:
                return UtilityClass.build_response(
                    de_range_mid_to_upper_threshold_percent*disposable_earning, disposable_earning, f"{CM.DISPOSABLE_EARNING} > {CM.MID_THRESHOLD_AMOUNT} and {CM.DISPOSABLE_EARNING} <= {CM.UPPER_THRESHOLD_AMOUNT}", f"{de_range_mid_to_upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")
            elif disposable_earning >= upper_threshold_amount:
                return UtilityClass.build_response(
                    upper_threshold_percent*disposable_earning, disposable_earning, CM.DE_GT_UPPER, f"{upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")

        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_minnesota: {str(e)}"
            )

    def cal_vermont(self, disposable_earning, is_consumer_debt, non_consumer_debt, exempt_amt_config):
        if non_consumer_debt == True:
            return self._general_debt_logic(
                disposable_earning, exempt_amt_config)
        elif is_consumer_debt == True:
            return self._minimum_wage_threshold_compare(
                disposable_earning, exempt_amt_config)
        return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER, CR.get_zero_withholding_response(CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT))
    
    def cal_arizona(self, disposable_earning,garn_start_date, exempt_amt_config):
        try:
            garn_start_date=self._gar_start_date_check(garn_start_date)
            if garn_start_date ==True:
                return self._minimum_wage_threshold_compare(
                    disposable_earning, exempt_amt_config)
            elif garn_start_date == False:
                return self._general_debt_logic(
                    disposable_earning, exempt_amt_config)
            
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in cal_arizona: {str(e)}"
            )
class CreditorDebtCalculator(StateWiseCreditorDebtFormulas):


    def calculate(self, record, config_data):
        """
        Main entry point for creditor debt calculation.
        Determines the state and applies the appropriate formula.
        """
        pay_period = record.get(EmployeeFields.PAY_PERIOD).lower()
        gross_pay = record.get(EmployeeFields.GROSS_PAY)
        home_state = StateAbbreviations(record.get(EmployeeFields.HOME_STATE)).get_state_name_and_abbr()
        no_of_exemption_including_self = record.get(
            EmployeeFields.NO_OF_EXEMPTION_INCLUDING_SELF)
        state = StateAbbreviations(record.get(
            EmployeeFields.WORK_STATE)).get_state_name_and_abbr()
        no_of_dependent_child = record.get(
            EmployeeFields.NO_OF_DEPENDENT_CHILD)
        filing_status = record.get(EmployeeFields.FILING_STATUS).lower()
        is_consumer_debt = record.get(EmployeeFields.IS_CONSUMER_DEBT)
        non_consumer_debt = record.get(EmployeeFields.NON_CONSUMER_DEBT)
        wages = record.get(CF.WAGES, 0)
        cs_helper=ChildSupportHelper(state)
        commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
        non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
        payroll_taxes = record.get(PT.PAYROLL_TAXES)
        gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
        mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
        disposable_earning = cs_helper.calculate_de(gross_pay, mandatory_deductions)

        garn_start_date=record.get(EmployeeFields.GARN_START_DATE)
        
        
        exempt_amt_config = self._exempt_amt_config_data(
            config_data, state, pay_period,garn_start_date,is_consumer_debt, non_consumer_debt,home_state)

        try:
            state_formulas = {
                ST.ARIZONA: lambda: self.cal_arizona(disposable_earning,garn_start_date, exempt_amt_config),
                ST.ALASKA: lambda: self.cal_alaska(home_state, disposable_earning, exempt_amt_config),
                ST.DELAWARE: lambda: self.cal_delaware(disposable_earning, exempt_amt_config),
                ST.HAWAII: lambda: self.cal_hawaii(disposable_earning, exempt_amt_config),
                ST.MAINE: lambda: self.cal_maine(disposable_earning, exempt_amt_config),
                ST.NORTH_DAKOTA: lambda: self.cal_north_dakota(disposable_earning, no_of_exemption_including_self, exempt_amt_config),
                ST.SOUTH_DAKOTA: lambda: self.cal_north_dakota(disposable_earning, no_of_exemption_including_self, exempt_amt_config),
                ST.MISSOURI: lambda: self.cal_missouri(disposable_earning, filing_status, exempt_amt_config),
                ST.NEBRASKA: lambda: self.cal_nebraska(disposable_earning, filing_status, exempt_amt_config),
                ST.TENNESSEE: lambda: self.cal_tennessee(disposable_earning, no_of_dependent_child, exempt_amt_config),
                ST.NEW_JERSEY: lambda: self.cal_new_jersey(gross_pay, exempt_amt_config),
                ST.NEVADA: lambda: self.cal_nevada(gross_pay, disposable_earning, exempt_amt_config),
                ST.MINNESOTA: lambda: self.cal_minnesota(
                    disposable_earning, exempt_amt_config),
                ST.VERMONT: lambda: self.cal_vermont(
                    disposable_earning, is_consumer_debt, non_consumer_debt, exempt_amt_config)
            }
            formula_func = state_formulas.get(state.lower().strip())


            if formula_func:
                return formula_func()

            else:
                _general_debt_logic = [
                    ST.ALABAMA, ST.ARKANSAS, ST.FLORIDA, ST.IDAHO, ST.MARYLAND,
                    ST.INDIANA, ST.KANSAS, ST.KENTUCKY, ST.LOUISIANA,
                    ST.MICHIGAN, ST.MISSISSIPPI, ST.MONTANA, ST.NEW_HAMPSHIRE,
                    ST.OHIO, ST.OKLAHOMA, ST.RHODE_ISLAND, ST.UTAH,
                    ST.WYOMING, ST.GEORGIA, ST.CALIFORNIA, ST.COLORADO
                ]
                _minimum_wage_threshold_compare_de = [
                     ST.IOWA, ST.WASHINGTON,ST.ILLINOIS, ST.CONNECTICUT, ST.NEW_MEXICO, ST.VIRGINIA, ST.WEST_VIRGINIA, ST.WISCONSIN]

                _minimum_wage_threshold_compare_gp = [
                    ST.NEW_YORK, ST.MASSACHUSETTS]

                if state in [ST.TEXAS, ST.NORTH_CAROLINA, ST.SOUTH_CAROLINA]:
                    return CC.NOT_PERMITTED
                elif state in _general_debt_logic:
                    return self._general_debt_logic(
                        disposable_earning, exempt_amt_config)
                elif state in _minimum_wage_threshold_compare_de:
                    return self._minimum_wage_threshold_compare(
                        disposable_earning, exempt_amt_config)
                elif state in _minimum_wage_threshold_compare_gp:
                    return self._minimum_wage_threshold_compare(
                        gross_pay,exempt_amt_config)
                else:
                    return CC.NOT_FOUND

        except Exception as e:
            import traceback as t
            # print("dddd",t.print_exc())
            return Response(
                {
                    "error": f"Exception in CreditorDebtCalculator.calculate: {str(e)}",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            )