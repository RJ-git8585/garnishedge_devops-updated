import logging
from processor.models import ThresholdAmount ,StateTaxLevyConfig
from rest_framework.response import Response
from rest_framework import status
from .child_support import  ChildSupportHelper
from processor.garnishment_library.utils import StateAbbreviations
from .creditor_debt import StateWiseCreditorDebtFormulas,CreditorDebtHelper
from user_app.constants import (
    StateList,
    StateTaxLevyCalculationData,
    EmployeeFields as EE,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    PayPeriodFields as PP,
    ExemptConfigFields as EC,
    CalculationMessages as CM,
    CommonConstants as CC,
    GarnishmentConstants as GC

)
import  traceback as t
from ..utils.response import UtilityClass, CalculationResponse
from processor.serializers.shared_serializers import ThresholdAmountSerializer
logger = logging.getLogger(__name__)


class StateTaxViewHelper:
    """
    Helper class for state tax levy calculations.
    """

    def cal_x_disposible_income(self, gross_pay, percent=0.25):
        """
        Calculate disposable income based on gross pay and percentage.
        """
        try:
            disposable_earnings = round(gross_pay, 2)
            monthly_garnishment_amount = disposable_earnings * percent
            return monthly_garnishment_amount
        except Exception as e:
            logger.error(f"Error calculating disposable income: {e}")
            return 0

    def fmv_threshold(self):
        """
        Set Fair Market Value thresholds for calculations.
        """
        self.lower_threshold_amount = StateTaxLevyCalculationData.FMW * GC.VALUE1
        self.upper_threshold_amount = StateTaxLevyCalculationData.FMW * GC.VALUE2
        self.threshold_53 = StateTaxLevyCalculationData.FMW *GC. VALUE3

    def get_wl_percent(self, state):
        """
        Get withholding limit percent and deduction basis for a state.
        """
        try:
            state = state.strip()
            obj = (
            StateTaxLevyConfig.objects
            .select_related("state")
            .filter(state__state__iexact=state)
            .first()
        )
            if obj.exists():
                return {
                    "wl_percent": obj[0].withholding_limit,
                    "deduct_from": obj[0].deduction_basis
                }
            return CC.NOT_FOUND
        except Exception as e:
            logger.error(
                f"Error fetching withholding percent for state {state}: {e}")
            return CC.NOT_FOUND

    def get_deduct_from(self, state):
        """
        Get deduction basis for a state.
        """
        try:
            obj = StateTaxLevyConfig.objects.filter(state=state)
            if obj.exists():
                return obj[0].deduction_basis
            return CC.NOT_FOUND
        except Exception as e:
            logger.error(
                f"Error fetching deduction basis for state {state}: {e}")
            return CC.NOT_FOUND

    def apply_general_debt_logic(self, disposable_earning, config_data, percent=GC.DEFAULT_PERCENT):
        """
        General logic for states using lower/upper threshold and percent.
        """
        try:
            lower = float(config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper = float(config_data[EC.UPPER_THRESHOLD_AMOUNT])

            if disposable_earning <= lower:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CalculationResponse.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                )
            elif lower <= disposable_earning <= upper:
                return UtilityClass.build_response(
                    disposable_earning - lower, disposable_earning,
                    CM.DE_GT_LOWER_LT_UPPER,
                    f"{CM.DISPOSABLE_EARNING} - {CM.UPPER_THRESHOLD_AMOUNT}"
                )
            return UtilityClass.build_response(
                percent * disposable_earning, disposable_earning,
                CM.DE_GT_UPPER, f"{percent * 100}% of {CM.DISPOSABLE_EARNING}"
            )
        except Exception as e:
            logger.error(f"Error in general debt logic: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))


class StateWiseStateTaxLevyFormulas(StateTaxViewHelper):
    """
    State-specific formulas for state tax levy calculations.
    """

    def cal_massachusetts(self, disposable_earning, gross_pay, config_data, percent=GC.MASSACHUSETTS_PERCENT):
        try:
            lower = float(config_data[EC.LOWER_THRESHOLD_AMOUNT])
            if disposable_earning <= lower:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CalculationResponse.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                )
            diff = disposable_earning - lower
            gp_percent = gross_pay * percent
            return UtilityClass.build_response(
                min(diff, gp_percent), disposable_earning,
                CM.DE_GT_LOWER,
                f"Min({percent * 100}% of {CM.GROSS_PAY}, ({CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT}))"
            )
        except Exception as e:
            logger.error(f"Error in Massachusetts formula: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))

    def cal_arizona(self, disposable_earning,garn_start_date,pay_period,state):
        try:
            filed_start =CreditorDebtHelper()._gar_start_date_check(garn_start_date)
            data = ThresholdAmount.objects.filter(
                                    config__pay_period__name__iexact=pay_period,
                                    config__state__state__iexact=state,config__start_gt_5dec24=filed_start

                                )
            serializer = ThresholdAmountSerializer(
                    data, many=True)
            return StateWiseCreditorDebtFormulas().cal_arizona(disposable_earning,garn_start_date, serializer.data[0])
        except Exception as e:
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))

    def cal_minnesota(self, disposable_earning, config_data, percent=GC.DEFAULT_PERCENT):
        try:
            upper = float(config_data[EC.UPPER_THRESHOLD_AMOUNT])
            if disposable_earning <= upper:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CalculationResponse.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.UPPER_THRESHOLD_AMOUNT)
                )
            diff = disposable_earning - upper
            de_percent = disposable_earning * percent
            return UtilityClass.build_response(
                min(de_percent, diff), disposable_earning,
                CM.DE_GT_UPPER,
                f"Min(({CM.DISPOSABLE_EARNING}-{CM.UPPER_THRESHOLD_AMOUNT}), {percent * 100}% of {CM.DISPOSABLE_EARNING})"
            )
        except Exception as e:
            logger.error(f"Error in Minnesota formula: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))

    def cal_newyork(self, disposable_earning, gross_pay, config_data,
                    percent1=GC.NEWYORK_PERCENT1, percent2=GC.NEWYORK_PERCENT2):
        try:
            lower = float(config_data[EC.LOWER_THRESHOLD_AMOUNT])
            if disposable_earning <= lower:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CalculationResponse.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                )
            de_percent = disposable_earning * percent2
            gp_percent = gross_pay * percent1
            return UtilityClass.build_response(
                min(de_percent, gp_percent), disposable_earning,
                CM.DE_GT_LOWER,
                f"Min({percent1 * 100}% of {CM.GROSS_PAY}, {percent2 * 100}% of {CM.DISPOSABLE_EARNING})"
            )
        except Exception as e:
            logger.error(f"Error in New York formula: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))

    def cal_west_virginia(self, no_of_exemption_including_self, net_pay, config_data):
        try:
            exempt_amt = GC.EXEMPT_AMOUNT
            lower = float(config_data[EC.LOWER_THRESHOLD_AMOUNT])


            if no_of_exemption_including_self == 0:
                return UtilityClass.build_response(
                    net_pay-lower, 0, CM.NO_OF_EXEMPTIONS_ONE,
                    CM.LOWER_THRESHOLD_AMOUNT
                )
            exempt_amt_cal = lower + (exempt_amt * (no_of_exemption_including_self))
            diff = net_pay - exempt_amt_cal

            return UtilityClass.build_response(
                diff, 0, CM.NO_OF_EXEMPTIONS_MORE,
                f"{EE.NET_PAY}-({CM.LOWER_THRESHOLD_AMOUNT}+{exempt_amt}*({CM.NO_OF_EXEMPTIONS_ONE}))"
            )
        except Exception as e:
            logger.error(f"Error in West Virginia formula: {e}")
            return UtilityClass.build_response(0, net_pay, "ERROR", str(e))

    def cal_new_mexico(self, disposable_earning, config_data, percent=GC.DEFAULT_PERCENT):
        try:
            upper = float(config_data[EC.UPPER_THRESHOLD_AMOUNT])
            if disposable_earning <= upper:
                return UtilityClass.build_response(
                    0, disposable_earning, CM.DE_LE_LOWER,
                    CalculationResponse.get_zero_withholding_response(
                        CM.DISPOSABLE_EARNING, CM.UPPER_THRESHOLD_AMOUNT)
                )
            diff = disposable_earning - upper
            de_percent = disposable_earning * percent
            return UtilityClass.build_response(
                min(de_percent, diff), disposable_earning,
                CM.DE_GT_UPPER,
                f"Min(({CM.DISPOSABLE_EARNING}-{CM.UPPER_THRESHOLD_AMOUNT}),{percent * 100}% of {CM.DISPOSABLE_EARNING})"
            )
        except Exception as e:
            logger.error(f"Error in New Mexico formula: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))

    def cal_delaware(self, disposable_earning, percent):
        try:
            return UtilityClass.build_response(
                disposable_earning * percent, disposable_earning,
                CM.NA, f"{percent * 100}% of {CM.DISPOSABLE_EARNING}"
            )
        except Exception as e:
            logger.error(f"Error in Delaware formula: {e}")
            return UtilityClass.build_response(0, disposable_earning, "ERROR", str(e))


class StateTaxLevyCalculator(StateWiseStateTaxLevyFormulas):
    """
    Main calculator for state tax levy, dispatching to state-specific logic.
    """

    def calculate(self, record, config_data):
        try:
            # Extract and validate required fields
            state = StateAbbreviations(record.get(
                EE.WORK_STATE, "")).get_state_name_and_abbr()
            gross_pay = record.get(EE.GROSS_PAY, 0)
            wages = record.get(CF.WAGES, 0)
            commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
            pay_period = record.get(EE.PAY_PERIOD.lower()).strip().lower()
            non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PT.PAYROLL_TAXES, {})
            cs_helper = ChildSupportHelper(state)
            gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
            disposable_earning = cs_helper.calculate_de(gross_pay, mandatory_deductions)
            pay_period = record.get(EE.PAY_PERIOD, "").lower()

            payroll_taxes = record.get(PT.PAYROLL_TAXES, {})
            no_of_exemption_including_self = record.get(
                EE.NO_OF_EXEMPTION_INCLUDING_SELF, 1)
            net_pay = record.get(EE.NET_PAY, 0)
            medical_insurance = payroll_taxes.get(
                CF.MEDICAL_INSURANCE, 0)
            garn_start_date = record.get(EE.GARN_START_DATE)

            # Helper to get exempt amount config for state and pay period
            def get_exempt_amt_config_data(config_data, state, pay_period):
                try:
                    return next(
                        i for i in config_data
                        if i[EE.STATE].lower() == state.lower() and i[EE.PAY_PERIOD].lower() == pay_period.lower()
                    )
                except StopIteration:
                    logger.error(
                        f"Exempt amount config not found for state '{state}' and pay period '{pay_period}'")
                    return None

            exempt_amt_config = get_exempt_amt_config_data(
                config_data, state, pay_period)

            # Helper to get percent for state
            def percent():
                wl = self.get_wl_percent(state.strip())
                try:
                    return round(float(wl["wl_percent"]) / 100, 2) if wl and "wl_percent" in wl else 0.25
                except Exception as e:
                    logger.error(
                        f"Error parsing percent for state {state}: {e}")
                    return 0.25

            # State-specific formula dispatch
            state_formulas = {
                StateList.ARIZONA: lambda: self.cal_arizona(disposable_earning,garn_start_date,pay_period,state),
                StateList.IDAHO: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.GEORGIA: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.COLORADO: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.ILLINOIS: lambda: UtilityClass.build_response(self.cal_x_disposible_income(gross_pay, percent()), 0, 
                        "NA", f"{percent() * 100}% of {CM.GROSS_PAY}"),
                StateList.MARYLAND: lambda: UtilityClass.build_response(self.cal_x_disposible_income(disposable_earning, percent()) 
                            - medical_insurance, disposable_earning, "NA", f"{percent() * 100}% of {CM.DISPOSABLE_EARNING}"),
                StateList.MASSACHUSETTS: lambda: self.cal_massachusetts(disposable_earning, gross_pay, exempt_amt_config, percent()),
                StateList.MISSOURI: lambda: UtilityClass.build_response(self.cal_x_disposible_income(disposable_earning, percent()),
                         disposable_earning, "NA", f"{percent() * 100}% of {CM.DISPOSABLE_EARNING}"),
                StateList.NEW_JERSEY: lambda: UtilityClass.build_response(self.cal_x_disposible_income(gross_pay, percent()), 
                            0, "NA", f"{percent() * 100}% of {CM.GROSS_PAY}"),
                StateList.MAINE: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.INDIANA: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.MINNESOTA: lambda: self.cal_minnesota(disposable_earning, exempt_amt_config, percent()),
                StateList.NEW_YORK: lambda: self.cal_newyork(disposable_earning, gross_pay, exempt_amt_config, percent()),
                StateList.NORTH_CAROLINA: lambda: UtilityClass.build_response(self.cal_x_disposible_income(gross_pay, percent()), 0, "NA", f"{percent() * 100}% of  {CM.GROSS_PAY}"),
                StateList.PENNSYLVANIA: lambda: UtilityClass.build_response(self.cal_x_disposible_income(gross_pay, percent()), 0, "NA", f"{percent() * 100}% of  {CM.GROSS_PAY}"),
                StateList.VERMONT: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.VIRGINIA: lambda: UtilityClass.build_response(self.cal_x_disposible_income(disposable_earning, percent()), disposable_earning, "NA", f"{percent() * 100}% of {CM.DISPOSABLE_EARNING}"),
                StateList.DELAWARE: lambda: self.cal_delaware(disposable_earning, percent()),
                StateList.IOWA: lambda: self.apply_general_debt_logic(disposable_earning, exempt_amt_config, percent()),
                StateList.WISCONSIN: lambda: UtilityClass.build_response(self.cal_x_disposible_income(gross_pay, percent()), 0, "NA", f"{percent() * 100}% of {CM.GROSS_PAY}"),
                StateList.WEST_VIRGINIA: lambda: self.cal_west_virginia(no_of_exemption_including_self, net_pay, exempt_amt_config),
                StateList.NEW_MEXICO: lambda: self.cal_new_mexico(
                    disposable_earning, exempt_amt_config, percent())
            }

            formula_func = state_formulas.get(state.lower())
            if formula_func:
                return formula_func()

            # Handle states with a flat 25% group
            twenty_five_percentage_grp_state = [
                StateList.ARKANSAS, StateList.KENTUCKY, StateList.OREGON,
                StateList.UTAH, StateList.CALIFORNIA, StateList.MONTANA,
                StateList.COLORADO, StateList.CONNECTICUT, StateList.LOUISIANA,
                StateList.MISSISSIPPI,
            ]
            if state in twenty_five_percentage_grp_state:
                result = self.cal_x_disposible_income(
                    disposable_earning, percent())
                return UtilityClass.build_response(result, disposable_earning, "NA", f"{percent() * 100}% of {CM.DISPOSABLE_EARNING}")
            elif state in [StateList.ALABAMA, StateList.HAWAII]:
                result = self.cal_x_disposible_income(gross_pay, percent())
                return UtilityClass.build_response(result, 0, "NA", f"{percent() * 100}% of {CM.GROSS_PAY}")

            logger.warning(f"No formula found for state: {state}")
            return CC.NOT_FOUND

        except Exception as e:

            logger.error(f"Error in state tax levy calculation: {e}")
            return Response(
                {
                    "error": str(e),
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            )
