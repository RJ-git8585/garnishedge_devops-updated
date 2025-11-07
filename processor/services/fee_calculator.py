"""
Garnishment fee calculation service.
Handles all fee-related calculations and validations.
"""

import logging
import math
from datetime import datetime, date
from typing import Dict, Any, Optional
from user_app.models import EmployeeDetail
from user_app.serializers import EmployeeDetailsSerializer
from processor.garnishment_library.calculations import GarFeesRulesEngine
from user_app.constants import (
    EmployeeFields as EE,
    ErrorMessages as EM
)

logger = logging.getLogger(__name__)


class FeeCalculator:
    """
    Service class for calculating garnishment fees and handling fee-related operations.
    """

    def __init__(self):
        self.logger = logger

    def _get_employee_details(self, employee_id: str) -> Optional[Dict]:
        """
        Fetches employee details by ID.
        Returns serialized data or None if not found.
        """
        try:
            obj = EmployeeDetail.objects.get(ee_id=employee_id)
            serializer = EmployeeDetailsSerializer(obj)
            return serializer.data
        except EmployeeDetail.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error fetching employee details for {employee_id}: {e}")
            return None

    def is_garnishment_fee_deducted(self, record: Dict) -> Optional[bool]:
        """
        Determines if garnishment fees can be deducted for the employee.
        Returns True, False, or None (if employee not found).
        """
        employee_data = self._get_employee_details(record[EE.EMPLOYEE_ID])
        if employee_data is None:
            return None
        
        suspended_till_str = employee_data.get('garnishment_fees_suspended_till')
        if not suspended_till_str:
            return True
        
        try:
            suspended_date = datetime.strptime(suspended_till_str, "%Y-%m-%d").date()
            return date.today() >= suspended_date
        except Exception as e:
            self.logger.warning(
                f"Malformed suspension date for employee {record[EE.EMPLOYEE_ID]}: {e}")
            return True

    def get_garnishment_fees(self, record: Dict, total_withhold_amt: float, garn_fees: Optional[float] = None) -> str:
        """
        Calculates garnishment fees based on employee data and suspension status.
        """
        is_deductible = self.is_garnishment_fee_deducted(record)
        employee_id = record.get(EE.EMPLOYEE_ID)
        work_state = record.get(EE.WORK_STATE)
        
        # Extract required fields for garnishment fees
        garnishment_type = ""
        pay_period = record.get(EE.PAY_PERIOD, "")
        
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
            if garnishment_data:
                garnishment_type = garnishment_data[0].get(EE.GARNISHMENT_TYPE, "")
        except (IndexError, KeyError):
            self.logger.warning(f"No garnishment data found for employee {employee_id}")
        
        try:
            if is_deductible is None:
                fees = GarFeesRulesEngine(work_state).apply_rule(
                    garnishment_type, pay_period, total_withhold_amt)
                return f"{fees}, {employee_id} is not registered. Please register the employee first to suspend garnishment fees calculation."
            elif is_deductible:
                return GarFeesRulesEngine(work_state).apply_rule(garnishment_type, pay_period, total_withhold_amt)
            else:
                employee_data = self._get_employee_details(employee_id)
                suspended_date = employee_data.get(
                    'garnishment_fees_suspended_till', 'N/A')
                return f"Garnishment fees cannot be deducted due to the suspension of garnishment fees until {suspended_date}"
        except Exception as e:
            self.logger.error(f"Error calculating garnishment fees for {employee_id}: {e}")
            return f"Error calculating garnishment fees: {e}"

    def get_rounded_garnishment_fee(self, work_state: str, garnishment_type: str, 
                                  pay_period: str, withholding_amt: float, 
                                  garn_fees: Optional[float] = None) -> Any:
        """
        Applies garnishment fee rule and rounds the result if it is numeric.
        """
        try:
            # Extract required fields for garnishment fees
            # If garn_fees is None or 0, use the rule engine to calculate the fee
            if garn_fees is None or math.isclose(garn_fees, 0.0, abs_tol=1e-9):
                fee = GarFeesRulesEngine(work_state).apply_rule(
                    garnishment_type, pay_period, withholding_amt)
                if isinstance(fee, (int, float)):
                    return round(fee, 2)
                return fee
            else:
                if garn_fees >= withholding_amt:
                    return f"{EM.GARNISHMENT_FEES_GTE_WITHHOLDING_AMT} Requested amount: ${garn_fees}, Withholding amount: ${withholding_amt}"
                else:
                    return garn_fees
        except Exception as e:
            self.logger.error(f"Error rounding garnishment fee: {e}")
            return f"Error calculating garnishment fee: {e}"

    def calculate_fees_for_multiple_garnishment(self, work_state: str, garnishment_type: str, 
                                               pay_period: str, withholding_amt: float, 
                                               garn_fees: Optional[float] = None) -> Any:
        """
        Calculate garnishment fees for multiple garnishment scenarios.
        """
        return self.get_rounded_garnishment_fee(
            work_state, garnishment_type, pay_period, withholding_amt, garn_fees
        )
