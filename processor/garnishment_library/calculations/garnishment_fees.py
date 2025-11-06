import logging
from typing import Any, Dict, Optional, Callable, List
from processor.models.garnishment_fees import GarnishmentFees
from processor.serializers.garnishment_fees_serializers import GarnishmentFeesSerializer
from user_app.constants import EmployeeFields, GarnishmentTypeFields
from processor.garnishment_library.utils  import StateAbbreviations

logger = logging.getLogger(__name__)

class GarFeesRulesEngine:
    """
    Engine to apply garnishment fee rules based on state, pay period, and garnishment type.
    """

    def __init__(self, work_state: str):
        self.work_state = StateAbbreviations(
            work_state).get_state_name_and_abbr().strip().lower()
        self._rules_data: Optional[List[Dict[str, Any]]] = None
        self._filtered_rules: Optional[List[Dict[str, Any]]] = None
        self.rule_map: Dict[str, Callable] = {
            f'Rule_{i}': getattr(self, f'Rule_{i}', self.undefined_rule) for i in range(1, 27)
        }

    def _load_rules(self) -> List[Dict[str, Any]]:
        """
        Loads and caches all garnishment fee rules from the database.
        
        """
        fees = (
            GarnishmentFees.objects
            .select_related("state", "garnishment_type", "pay_period", "rule")
            .filter(state__state__iexact=self.work_state)
            .order_by("-created_at")
        )
        serializer = GarnishmentFeesSerializer(fees, many=True)
        
        return serializer.data

    def _get_filtered_rule(self, garnishment_type: str, pay_period: str) -> Optional[Dict[str, Any]]:
        """
        Filters rules based on state, pay period, and garnishment type.
        """
        try:
            garn_type = garnishment_type.strip().lower()
            pay_period_lower = pay_period.strip().lower()

            if self._filtered_rules is None:
                self._filtered_rules = [
                    item for item in self._load_rules()
                    if item.get("pay_period", "").strip().lower() == pay_period_lower
                    and item.get("garnishment_type", "").strip().lower() == garn_type
                ]
            return self._filtered_rules[0] if self._filtered_rules else None
        except Exception as e:
            logger.error(f"Error filtering rules: {e}")
            return None

    def find_rule(self, garnishment_type: str, pay_period: str) -> Optional[str]:
        """
        Finds the rule name for the given garnishment type and pay period.
        """
        item = self._get_filtered_rule(garnishment_type, pay_period)
        return item.get("rule") if item else None

    def get_payable_name(self, rule_name: str,garn_fees:List[Dict[str, Any]]=None) -> Optional[str]:
        """
        Returns the 'payable_by' field for a given rule name.
        """
        try:
            for item in self._load_rules():
                if item.get("rule", "").strip().title() == rule_name:
                    return item.get("payable_by")
        except Exception as e:

            logger.error(
                f"Error getting payable name for rule {rule_name}: {e}")
        return None

    def calculate_rule(self, withhold_amt: float, percentage: float, min_value: float = 0) -> float:
        """
        Calculates the fee based on a percentage of the withheld amount, with a minimum value.
        """
        try:
            return round(max(min_value, withhold_amt * percentage if withhold_amt else 0), 1)
        except Exception as e:
            logger.error(f"Error calculating rule: {e}")
            return 0.0

    def apply_rule(self, garnishment_type: str, pay_period: str, withhold_amt: float, garn_fees=None) -> Any:
        """
        Applies the appropriate rule based on garnishment type and pay period.
        """
        rule_name = self.find_rule(garnishment_type, pay_period)
        if not rule_name:
            logger.warning("No rule found for the given garnishment type and pay period.")
            return "No applicable rule found"
        rule_func = self.rule_map.get(rule_name)
        if not rule_func:
            logger.error(f"Rule '{rule_name}' is not implemented.")
            return f"Rule '{rule_name}' is not implemented."
        try:
            return rule_func(garnishment_type, pay_period, withhold_amt)
        except Exception as e:
            logger.error(f"Error applying rule '{rule_name}': {e}")
            return f"Error applying rule '{rule_name}': {e}"

    def undefined_rule(self, *args, **kwargs):
        return "This rule is not defined."

    def Rule_1(self, garnishment_type, pay_period, withhold_amt):
        item = self._get_filtered_rule(garnishment_type, pay_period)
        if item:
            try:
                amount = item.get('amount', 0)
                payable = self.get_payable_name('Rule_1')
                return f"${amount}, Payable by {payable}"
            except Exception as e:
                logger.error(f"Error in Rule_1: {e}")
                return "Error in Rule 1"
        return "Rule 1 data not found"

    def Rule_2(self, *_): return "No Provision"

    def Rule_3(self, garnishment_type, pay_period, withhold_amt):
        item = self._get_filtered_rule(garnishment_type, pay_period)
        if not item:
            return "Rule 3 data not found"
        try:
            garn_type = garnishment_type.strip().lower()
            amt = withhold_amt * 0.10
            if garn_type == GarnishmentTypeFields.STATE_TAX_LEVY:
                return amt if amt < 50 else 0
            elif garn_type == GarnishmentTypeFields.CREDITOR_DEBT:
                return amt if 50 <= amt < 100 else 0
            return 0
        except Exception as e:
            logger.error(f"Error in Rule_3: {e}")
            return "Error in Rule 3"

    def Rule_4(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.020)}, Payable by {self.get_payable_name('Rule_4')}"

    def Rule_5(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.030, 12)}, Payable by {self.get_payable_name('Rule_5')}"

    def Rule_6(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.020, 8)}, Payable by {self.get_payable_name('Rule_6')}"

    def Rule_7(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.010, 2)}, Payable by {self.get_payable_name('Rule_7')}"

    def Rule_8(self, *_):
        return ("Income submitted by electronic means: $1 each payment, not to exceed $2/month. "
                "Other means: $2 each payment, not to exceed $4/month")

    def Rule_9(self, *_): return "5% of amount deducted from creditor funds"

    def Rule_10(self, *_): return "Court will award you cost"

    def Rule_11(self, *_): return "Rule 11 is not defined"

    def Rule_12(    
        self, *_): return "$2 for each deduction taken after levy expiry/release"

    def Rule_13(self, garnishment_type, pay_period, withhold_amt):
        return f"${round(withhold_amt * 0.02, 1)}, Payable by {self.get_payable_name('Rule_13')}"

    def Rule_14(self, garnishment_type, pay_period, withhold_amt):
        return f"${round(withhold_amt * 0.02, 1)}, Payable by {self.get_payable_name('Rule_14')}"

    def Rule_15(self, *_): return "$5 from landlord amount"

    def Rule_16(self, *_): return "$5 for each garnishment served"

    def Rule_17(self, *_): return "$15 paid by creditor"

    def Rule_18(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.050, 5)}, Payable by {self.get_payable_name('Rule_18')}"

    def Rule_19(self, *_): return "May deduct $5.00 for state employees"

    def Rule_20(
        self, *_): return "$10.00/month under wage attachments (e.g. student loans)"

    def Rule_21(
        self, *_): return "$10 for single garnishment, $25 for continuing garnishment, paid by creditor"

    def Rule_22(self, *_): return "$10 or $50 paid by creditor"

    def Rule_23(self, *_): return "Rule 23 is not defined"

    def Rule_24(self, *_): return "Rule 24 is not defined"

    def Rule_25(self, *_): return "Rule 25 is not defined"

    def Rule_26(self, garnishment_type, pay_period, withhold_amt):
        return f"${self.calculate_rule(withhold_amt, 0.01)}, Payable by {self.get_payable_name('Rule_26')}"
