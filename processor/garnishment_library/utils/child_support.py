import logging
from user_app.constants import PayPeriodFields as PP
import traceback as t
from decimal import Decimal, ROUND_HALF_UP

FMW_RATE = 7.25
PAY_PERIOD_MULTIPLIER = {
    PP.WEEKLY: 30,
    PP.BI_WEEKLY: 60,
    PP.SEMI_MONTHLY: 65,
    PP.MONTHLY: 130,
}

# Configure logging
logger = logging.getLogger(__name__)


class Helper:

    def get_support_amounts_by_type(self, garnishment_data, amount_type):
        """
        Retrieves a list of amounts from the record based on the provided amount_type.

        :param record: The data record containing garnishment information.
        :param amount_type: The prefix key to filter amounts (e.g., 'ordered_amount' or 'arrear_amount').
        :return: List of filtered amount values.
        """
        try:
            return [
                float(val) for item in garnishment_data[0]["data"]
                for key, val in item.items()
                if key.lower().startswith(amount_type.lower())
            ]
        except Exception as e:
            raise ValueError(f"Error extracting amounts for type '{amount_type}': {str(e)}")
        

    def calculate_each_amount(self, amounts, label):
        """
        Returns a dictionary of each amount keyed by order and type (e.g., child support or arrears).
       
        """
        try:
            return {
                f"{label}{i+1}": float(amt)
                for i, amt in enumerate(amounts)
            }
        except Exception as e:
            raise ValueError(
                f"Error calculating each {label}: {str(e)}"
            )
