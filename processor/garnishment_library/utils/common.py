from django.core.exceptions import ObjectDoesNotExist
from processor.models import *
import logging
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from user_app.constants import PayPeriodFields as PP

from rest_framework.pagination import PageNumberPagination
import traceback as t
from typing import Dict
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

FMW_RATE = 7.25
PAY_PERIOD_MULTIPLIER = {
    PP.WEEKLY: 30,
    PP.BI_WEEKLY: 60,
    PP.SEMI_MONTHLY: 65,
    PP.MONTHLY: 130,
}

# Configure logging
logger = logging.getLogger(__name__)



class FinanceUtils:
    
    def round_decimal(d: Decimal) -> Decimal:
        """
        Rounds a Decimal to 2 decimal places using ROUND_HALF_UP.
        """
        return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    

    def _convert_result_structure(self, result_dict:Dict)-> Dict:
        """
        Convert any nested Decimal values to float in result structure
        """
        converted = {}
        for key, value in result_dict.items():
            if isinstance(value, dict):
                converted[key] = self._convert_result_structure(value)
            elif isinstance(value, Decimal):
                converted[key] = float(value)
            elif isinstance(value, list):
                converted[key] = [float(item) if isinstance(item, Decimal) else item for item in value]
            else:
                converted[key] = float(value)
        return converted

class ExemptAmount:

    def get_fmw(self, pay_period):
        """
        Returns the Federal Minimum Wage threshold for the given pay period.
        """
        if not pay_period:
            raise ValueError("Pay period is missing in the record.")
        multiplier = PAY_PERIOD_MULTIPLIER.get(pay_period.lower())
        if not multiplier:
            raise ValueError(f"Invalid pay period: {pay_period}")
        return FMW_RATE * multiplier
    
class AllocationMethodResolver:
    
    """
    Identifies the allocation method for a given work state using the database.
    """

    def __init__(self, work_state):
        # Normalize and lower the state name or abbreviation
        self.work_state = StateAbbreviations(work_state).get_state_name_and_abbr().lower()

    def get_allocation_method(self):
        """
        Fetches the allocation method from the WithholdingRules table based on the work state.
        """
        try:
            rule = WithholdingRules.objects.get(state__state__iexact=self.work_state)
            if rule.allocation_method:
                return rule.allocation_method.lower()
            return f"No allocation method defined for the state: {self.work_state.capitalize()}."
        
        except ObjectDoesNotExist:
            return f"No withholding rule found for the state: {self.work_state.capitalize()}."
        
        except MultipleObjectsReturned:
            return f"Multiple withholding rules found for the state: {self.work_state.capitalize()}. Please verify data integrity."
        
        except Exception as e:
            return f"Unexpected error while fetching allocation method: {str(e)}"
        

class WLIdentifier:
    """
    Identifies withholding limits for a given state and employee using database models.
    """

    def get_state_rule(self, work_state):
        """
        Returns the WithholdingRules object for the given state abbreviation.
        """
        try:
            work_state_name = StateAbbreviations(work_state).get_state_name_and_abbr()
            
            rule_obj = WithholdingRules.objects.filter(
                state__state__iexact=work_state_name
            ).first()
            if not rule_obj:
                raise ValueError(f"No rule found for the state: {work_state_name}")

            return rule_obj

        except Exception as e:
            raise RuntimeError(f"Error retrieving rule for state '{work_state}': {e}")
        

    def find_wl_value(self, work_state, employee_id, supports_2nd_family, arrears_of_more_than_12_weeks, de_gt_145, order_gt_one,issuing_state,work_states):
        """
        Finds the withholding limit (WL) value based on state rule and employee attributes.
        """
        try:
            rule_obj = self.get_state_rule(work_state)

            filters = {
                "rule": int(rule_obj.rule), 
                "supports_2nd_family": supports_2nd_family,
                "arrears_of_more_than_12_weeks": arrears_of_more_than_12_weeks,
                "number_of_orders": order_gt_one, 
                "weekly_de_code": de_gt_145, 
                "issuing_state": issuing_state,
                "work_state":work_states
            }

            if order_gt_one:
                filters["number_of_orders"] = order_gt_one
            if de_gt_145:
                filters["weekly_de_code"] = de_gt_145


            limit = WithholdingLimit.objects.filter(**filters).first()
            
            if not limit:
                raise ValueError(f"No matching WL found for employee {employee_id} with filters {filters}")
            
            return int(limit.wl) / 100

        except Exception as e:
            raise RuntimeError(f"Error finding WL value: {e}")


def change_record_case(record):
    """
    Converts all keys in the record to snake_case and lower case.

    """
    try:
        new_record = {}
        for key, value in record.items():
            new_key = key.replace(' ', '_').lower()
            new_record[new_key] = value
        return new_record
    except Exception as e:
        raise ValueError(f"Error changing record case: {e}")


class StateAbbreviations:
    """
    Utility for converting state abbreviations to full state names.

    """

    def __init__(self, abbreviation):
        self.abbreviation = abbreviation.lower()

    def get_state_name_and_abbr(self):
        """
        Returns the full state name for a given abbreviation, or the input if not found.
        """
        state_abbreviations = {
            "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas",
            "ca": "california", "co": "colorado", "ct": "connecticut", "de": "delaware",
            "fl": "florida", "ga": "georgia", "hi": "hawaii", "id": "idaho",
            "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas",
            "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland",
            "ma": "massachusetts", "mi": "michigan", "mn": "minnesota", "ms": "mississippi",
            "mo": "missouri", "mt": "montana", "ne": "nebraska", "nv": "nevada",
            "nh": "new hampshire", "nj": "new jersey", "nm": "new mexico", "ny": "new york",
            "nc": "north carolina", "nd": "north dakota", "oh": "ohio", "ok": "oklahoma",
            "or": "oregon", "pa": "pennsylvania", "ri": "rhode island", "sc": "south carolina",
            "sd": "south dakota", "tn": "tennessee", "tx": "texas", "ut": "utah",
            "vt": "vermont", "va": "virginia", "wa": "washington", "wv": "west virginia",
            "wi": "wisconsin", "wy": "wyoming"
        }
        if len(self.abbreviation) != 2:
            state_name = self.abbreviation
        else:
            state_name = state_abbreviations.get(
                self.abbreviation, self.abbreviation)
        return state_name
    

class PaginationHelper:
    @staticmethod
    def paginate_queryset(queryset, request, serializer_class):
        paginator = PageNumberPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = serializer_class(paginated_queryset, many=True)

        return {
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer.data
        }




