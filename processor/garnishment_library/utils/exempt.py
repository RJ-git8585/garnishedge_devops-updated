from ast import Try
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
from datetime import datetime, date
import traceback as t

class ExemptHelper():
    """
    Helper class for general creditor debt logic.
    
    """
    
    def _gar_start_date_check(self,garn_start_date):
        """
        Ensures garn_start_date is in MM/DD/YYYY format.
        If it's already correct, it won't modify it.
        """
        if not garn_start_date:
            return None

        # If it's already a date or datetime object, convert to MM/DD/YYYY string
        if isinstance(garn_start_date, (date, datetime)):
            return garn_start_date.strftime("%m/%d/%Y")

        # Check if the date is already in MM/DD/YYYY formatc
        try:
            datetime.strptime(garn_start_date, "%m/%d/%Y")
            # If parsing succeeds, it's already in correct format, return as string
            formatted_date = garn_start_date
        except ValueError:
            # If parsing fails, try replacing - with / and convert
            garn_start_date = garn_start_date.replace("-", "/")
            formatted_date = datetime.strptime(garn_start_date, "%m/%d/%Y").strftime("%m/%d/%Y")

        return formatted_date
        
    def _exempt_amt_config_data(self, config_data, state, pay_period, garn_start_date, 
                            is_consumer_debt=None, non_consumer_debt=None, 
                            home_state=None, ftb_type=None):
        """
        Helper to fetch the correct config for the state, pay period, and optionally debt type.
        Now supports date-range matching for states like Oregon and Arizona.
        """

        if is_consumer_debt==True:
            debt_type = "consumer"
        elif non_consumer_debt==True :
            debt_type = "non consumer"
        else:
            debt_type = None

        if home_state and home_state.lower() == "alaska":
            home_state = "alaska"
        else:
            home_state = None
        
        # Parse garnishment start date if provided
        garn_start_date_parsed = None
        if garn_start_date:
            try:
                garn_start_date_normalized = garn_start_date.replace("-", "/")
                garn_start_date_parsed = datetime.strptime(garn_start_date_normalized, "%m/%d/%Y").date()
            except:
                pass

        try:
            # Step 1: Get all matching configs
            matching_configs = []
            for i in config_data:
                # Check basic filters
                state_match = i[EmployeeFields.STATE].lower() == state.lower()
                period_match = i[EmployeeFields.PAY_PERIOD].lower() == pay_period.lower()
                # Debt type filter: config.debt_type must be None OR match the requested debt_type
                debt_match = (
                    i.get("debt_type") is None 
                    or not i.get("debt_type") 
                    or (debt_type and i.get("debt_type", "").lower() == debt_type)
                )
                
                # Home state filter: config.home_state must be None OR match the requested home_state
                home_match = (
                    i.get("home_state") is None 
                    or (home_state and i.get("home_state") == home_state)
                )
                
                # FTB type filter: config.ftb_type must be None OR match the requested ftb_type
                ftb_match = (
                    i.get("ftb_type") is None 
                    or (ftb_type and i.get("ftb_type") == ftb_type)
                )
                
                if not (state_match and period_match and debt_match and home_match and ftb_match):
                    continue
                
                # Date filtering: handle both simple (NULL date) and date-based configs
                config_date_str = i.get("garn_start_date")
                
                # If config has no date, it's a default/fallback - always include
                if config_date_str is None or not isinstance(config_date_str, str) or not config_date_str.strip():
                    matching_configs.append(i)
                    continue
                
                # If we have a garnishment date, do range matching
                if garn_start_date_parsed:
                    try:
                        config_date_normalized = config_date_str.replace("-", "/")
                        # Try MM/DD/YYYY format first
                        try:
                            config_date = datetime.strptime(config_date_normalized, "%m/%d/%Y").date()
                        except ValueError:
                            # Try YYYY/MM/DD format
                            config_date = datetime.strptime(config_date_normalized, "%Y/%m/%d").date()
                        
                        # Include configs where effective date <= garnishment date
                        if config_date <= garn_start_date_parsed:
                            matching_configs.append(i)
                    except ValueError:
                        # Skip configs with unparseable dates
                        continue
                # If no garnishment date provided, skip date-specific configs
            if not matching_configs:
                return None
            
            # Step 2: Return the config with the most recent effective date and highest specificity
            def get_config_priority(config):
                """
                Helper to get config's priority for sorting.
                Returns tuple: (date, specificity_score)
                - Higher dates win first
                - If dates are equal, higher specificity wins
                """
                # Get effective date
                date_str = config.get("garn_start_date")
                if not date_str or not isinstance(date_str, str):
                    effective_date = date.min  # NULL dates get lowest date priority
                else:
                    try:
                        date_str = date_str.replace("-", "/")
                        try:
                            effective_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                        except ValueError:
                            effective_date = datetime.strptime(date_str, "%Y/%m/%d").date()
                    except ValueError:
                        effective_date = date.min
                
                # Calculate specificity score (higher = more specific)
                # Configs with specific values for optional fields are more specific
                specificity = 0
                if config.get("debt_type") is not None and config.get("debt_type"):
                    specificity += 1
                if config.get("home_state") is not None and config.get("home_state"):
                    specificity += 1
                if config.get("ftb_type") is not None and config.get("ftb_type"):
                    specificity += 1
                
                return (effective_date, specificity)
            
            # Return the most recent and most specific applicable config
            return max(matching_configs, key=get_config_priority)

        except Exception as e:
            return Response({
                "error": f"Exception in _exempt_amt_config_data: {str(e)}"
            })

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
            lower_threshold_amount =float(
                config_data[EC.LOWER_THRESHOLD_AMOUNT])
            upper_threshold_amount = float(
                config_data[EC.UPPER_THRESHOLD_AMOUNT])
            upper_threshold_percent = float(
                config_data[EC.UPPER_THRESHOLD_PERCENT]) / 100
            de_range_lower_to_upper_threshold_percent = float(
                config_data[EC.DE_RANGE_LOWER_TO_UPPER_THRESHOLD_PERCENT]) / 100
            
            if disposable_earning <= lower_threshold_amount:
                return UtilityClass.build_response(0, disposable_earning, CM.DE_LE_LOWER, 
                                                   CR.get_zero_withholding_response(
                                                       CM.DISPOSABLE_EARNING, CM.LOWER_THRESHOLD_AMOUNT)
                                        )
            elif lower_threshold_amount < disposable_earning <= upper_threshold_amount:
                withholding_amount = (disposable_earning - lower_threshold_amount) * de_range_lower_to_upper_threshold_percent
                return UtilityClass.build_response(withholding_amount, disposable_earning,
                                                    CM.DE_GT_LOWER_LT_UPPER, f"({CM.DISPOSABLE_EARNING} - {CM.LOWER_THRESHOLD_AMOUNT}) * {de_range_lower_to_upper_threshold_percent*100}%")
            elif disposable_earning > upper_threshold_amount:
                withholding_amount = upper_threshold_percent * disposable_earning
                return UtilityClass.build_response(withholding_amount, disposable_earning, CM.DE_GT_UPPER, f"{upper_threshold_percent*100}% of {CM.DISPOSABLE_EARNING}")
        
        except Exception as e:
            return UtilityClass.build_response(
                0, disposable_earning, "ERROR",
                f"Exception in _general_debt_logic: {str(e)}"
            )
