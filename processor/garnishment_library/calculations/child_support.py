import os
import json
from django.conf import settings
from processor.garnishment_library.utils import AllocationMethodResolver,StateAbbreviations,WLIdentifier
from user_app.constants import (
    EmployeeFields, CalculationFields, PayrollTaxesFields,
    JSONPath, AllocationMethods
)
import traceback as t
from processor.garnishment_library.utils import Helper


class ChildSupportHelper:
    """
    Handles child support garnishment calculations, including disposable earnings,
    withholding limits, and allocation methods.
    """

    def __init__(self, work_state):
        self.de_rules_file = os.path.join(
            settings.BASE_DIR, 'user_app', JSONPath.DISPOSABLE_EARNING_RULES
        )
        self.work_state = StateAbbreviations(
            work_state
        ).get_state_name_and_abbr()

    def _support_amount(self, garnishment_data, amount_type):
        """Extract support amounts by type from garnishment data"""
        support_amount = Helper().get_support_amounts_by_type(garnishment_data, amount_type)
        return support_amount
    
    def _calculate_each_amount(self,amounts, label):
        amount =Helper().calculate_each_amount( amounts, label)
        return amount
        
    def _load_json_file(self, file_path):
        """
        Loads and parses a JSON file.
        Raises descriptive exceptions on failure.
        """
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON format in file: {file_path} ({str(e)})")

    def calculate_deduction_rules(self):
        """
        Retrieves deduction rules for the current work state.
        """
        if not self.work_state:
            raise ValueError("State information is missing in the record.")
        data = self._load_json_file(self.de_rules_file)
        for rule in data.get("de", []):
            if rule['State'].lower() == self.work_state.lower():
                return rule['taxes_deduction']
        raise ValueError(f"No DE rule found for state: {self.work_state}")

    def get_mapping_keys(self):
        """
        Maps deduction rule keys to actual payroll tax keys.
        """
        keys = self.calculate_deduction_rules()
        actual_keys = self._load_json_file(
            self.de_rules_file).get("mapping", [])
        # Map each key to its corresponding value in the mapping, or keep the key if not found
        return [next((d[key] for d in actual_keys if key in d), key) for key in keys]

    def calculate_md(self, payroll_taxes):
        """
        Calculates mandatory deductions based on payroll taxes and deduction rules.
        Args:
            payroll_taxes (dict): Dictionary containing payroll tax amounts
        """
        if payroll_taxes is None:
            raise ValueError(f"Missing payroll taxes data.")

        de_keys = self.get_mapping_keys()
        try:
            return sum(payroll_taxes.get(key, 0) for key in de_keys)
        except Exception as e:
            raise ValueError(
                f"Error calculating mandatory deductions: {str(e)}")

    def calculate_gross_pay(self, wages, commission_and_bonus, non_accountable_allowances):
        """
        Calculates gross pay as the sum of wages, commissions/bonuses, and non-accountable allowances.
        Args:
            wages (float): Wage amount
            commission_and_bonus (float): Commission and bonus amount
            non_accountable_allowances (float): Non-accountable allowances amount
        """
        try:
            return wages + commission_and_bonus + non_accountable_allowances
        except Exception as e:
            raise ValueError(f"Error calculating gross pay: {str(e)}")

    def calculate_de(self, gross_pay, mandatory_deductions):
        """
        Calculates disposable earnings (gross pay minus mandatory deductions).
        Args:
            gross_pay (float): Total gross pay
            mandatory_deductions (float): Total mandatory deductions
        """
        try:
            return (float(gross_pay) - float(mandatory_deductions))
        except Exception as e:
            raise ValueError(
                f"Error calculating disposable earnings: {str(e)}")

    def calculate_wl(self, employee_id, supports_2nd_family, arrears_12ws, disposable_earnings, garnishment_data,issuing_state):
        """
        Calculates the withholding limit (WL) for the employee based on state rules from the DB.
        Args:
            employee_id (str): Employee ID
            supports_2nd_family (str): Whether employee supports second family
            arrears_12ws (str): Whether arrears are greater than 12 weeks
            disposable_earnings (float): Calculated disposable earnings
            garnishment_data (list): Garnishment data for calculating order count
        """
        try:
            rule_obj = WLIdentifier().get_state_rule(self.work_state)
            rule_number = rule_obj.rule
            ordered_amounts = self._support_amount(garnishment_data, CalculationFields.ARREAR_AMOUNT)
            order_count = len(ordered_amounts)

            if int(rule_number) == 6:
                de_gt_145 = "LE_145" if disposable_earnings <= int(145) else "GT_145"
            else:
                de_gt_145 = None

            arrears_12w_n = None if int(rule_number) == 4 or int(rule_number) == 2 or int(rule_number) == 3 else arrears_12ws
            
            if int(rule_number) == 4:
                order_gt_one = "Single" if int(rule_number) == 4 and order_count <= 1 else "Multiple"
            else:
                order_gt_one = None

            supports_2nd_family = None if int(rule_number) == 2 or int(rule_number) == 3 else supports_2nd_family

            work_states = "missouri" if self.work_state=="missouri" else None
            issuing_state = "missouri" if issuing_state=="missouri" else None
            
            return WLIdentifier().find_wl_value(
                work_state=self.work_state,
                employee_id=employee_id,
                supports_2nd_family=supports_2nd_family,
                arrears_of_more_than_12_weeks=arrears_12w_n,
                de_gt_145=de_gt_145,
                order_gt_one=order_gt_one,
                issuing_state=issuing_state,
                work_states=work_states
            )

        except Exception as e:
            raise ValueError(f"Error calculating withholding limit: {str(e)}")

    def calculate_twa(self, support_amounts, arrear_amounts):
        """
        Calculates the total withholding amount (TWA) as the sum of support and arrear amounts.
        Args:
            support_amounts (list): List of support amounts
            arrear_amounts (list): List of arrear amounts
        """
        try:
            return sum(support_amounts) + sum(arrear_amounts)
        except Exception as e:
            raise ValueError(
                f"Error calculating total withholding amount: {str(e)}")

    def calculate_ade(self, withholding_limit, disposable_earnings):
        """
        Calculates the allowable disposable earnings (ADE).
        Args:
            withholding_limit (float): Calculated withholding limit
            disposable_earnings (float): Calculated disposable earnings
        """
        try:
            ade = withholding_limit * disposable_earnings
            return round(ade, 1)
        except Exception as e:
            raise ValueError(
                f"Error calculating allowable disposable earnings: {str(e)}")

    def calculate_wa(self, allowable_de, support_amounts):
        """
        Calculates the withholding amount (WA) as the minimum of ADE and total support amount.
        Args:
            allowable_de (float): Allowable disposable earnings
            support_amounts (list): List of support amounts
        """
        try:
            return min(allowable_de, sum(support_amounts))
        except Exception as e:
            raise ValueError(f"Error calculating withholding amount: {str(e)}")
        


    def calculate_each_child_support_amt(self, support_amounts):
        """
        Returns a dictionary of each child support amount keyed by order.
        Args:
            support_amounts (list): List of support amounts
        """
        try:
            return {
                f"child support amount{i+1}": amt
                for i, amt in enumerate(support_amounts)
            }
        except Exception as e:
            raise ValueError(
                f"Error calculating each child support amount: {str(e)}")

    def calculate_each_arrears_amt(self, arrear_amounts):
        """
        Returns a dictionary of each arrear amount keyed by order.
        Args:
            arrear_amounts (list): List of arrear amounts
        """
        try:
            return {
                f"arrear amount{i+1}": amt
                for i, amt in enumerate(arrear_amounts)
            }
        except Exception as e:
            raise ValueError(
                f"Error calculating each arrears amount: {str(e)}")
        

class SingleChild(ChildSupportHelper):
    """
    Handles calculation for a single child support order.
    """

    def calculate(self, record):
        try:
            # Extract required values from record
            
            wages = record.get(CalculationFields.WAGES, 0)
            commission_and_bonus = record.get(CalculationFields.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = record.get(CalculationFields.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PayrollTaxesFields.PAYROLL_TAXES)
            issuing_state = record.get(EmployeeFields.ISSUING_STATE)
            employee_id = record.get(EmployeeFields.EMPLOYEE_ID)
            supports_2nd_family = record.get(EmployeeFields.SUPPORT_SECOND_FAMILY)
            arrears_12ws = record.get(EmployeeFields.ARREARS_GREATER_THAN_12_WEEKS)
            garnishment_data = record.get('garnishment_data', [])
            
            # Calculate intermediate values
            gross_pay = self.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = self.calculate_md(payroll_taxes)
            de = self.calculate_de(gross_pay, mandatory_deductions)
            withholding_limit = self.calculate_wl(employee_id, supports_2nd_family, arrears_12ws, de, garnishment_data,issuing_state)
            print("withholding_limit",withholding_limit)
            ade = self.calculate_ade(withholding_limit, de)
            
            # Get support amounts
            child_amt = self._support_amount(garnishment_data, CalculationFields.ORDERED_AMOUNT)[0]
            arrear_amt = self._support_amount(garnishment_data, CalculationFields.ARREAR_AMOUNT)[0]
            
            withholding = min(ade, child_amt)
            remaining = max(0, ade - child_amt)
            arrear = min(arrear_amt, remaining) if ade > child_amt else 0

            return {
                "result_amt": {"child support amount1": round(withholding, 2) if gross_pay > 0 else 0},
                "arrear_amt": {"arrear amount1": round(arrear, 2) if gross_pay > 0 else 0},
                "ade": ade,
                "de": de,
                "mde": mandatory_deductions
            }
        except Exception as e:
            raise ValueError(f"Error in SingleChild calculation: {str(e)}")


class MultipleChild(ChildSupportHelper):
    """
    Handles calculation for multiple child support orders, including allocation methods.
    """

    def calculate(self, record):
        try:
            # Extract required values from record
            wages = record.get(CalculationFields.WAGES, 0)
            commission_and_bonus = record.get(CalculationFields.COMMISSION_AND_BONUS, 0)
            non_accountable_allowances = record.get(CalculationFields.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PayrollTaxesFields.PAYROLL_TAXES)
            employee_id = record.get(EmployeeFields.EMPLOYEE_ID)
            supports_2nd_family = record.get(EmployeeFields.SUPPORT_SECOND_FAMILY)
            arrears_12ws = record.get(EmployeeFields.ARREARS_GREATER_THAN_12_WEEKS)
            garnishment_data = record.get('garnishment_data')
            issuing_state = record.get(EmployeeFields.ISSUING_STATE)

            # Calculate intermediate values
            gross_pay = self.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
            mandatory_deductions = self.calculate_md(payroll_taxes)
            de = self.calculate_de(gross_pay, mandatory_deductions)
            withholding_limit = self.calculate_wl(employee_id, supports_2nd_family, arrears_12ws, de, garnishment_data,issuing_state)
            ade = self.calculate_ade(withholding_limit, de)

            # Get support amounts ONCE - avoid redundant calculations
            tcsa = self._support_amount(garnishment_data, CalculationFields.ORDERED_AMOUNT)
            taa = self._support_amount(garnishment_data, CalculationFields.ARREAR_AMOUNT)
            
            # Calculate TWA and WA using already extracted amounts
            twa = self.calculate_twa(tcsa, taa)
            wa = self.calculate_wa(ade, tcsa)
            
            alloc_method = AllocationMethodResolver(
                self.work_state
            ).get_allocation_method()
            print("alloc_method",alloc_method)
            if ade >= twa:
                cs_amounts = self._calculate_each_amount(tcsa,"child support amount") 
                ar_amounts = self._calculate_each_amount(tcsa,"arrear amount") 
            else:
                cs_amounts, ar_amounts = {}, {}
                if alloc_method == AllocationMethods.PRORATE:
                    # Prorate support amounts
                    cs_amounts = {
                        f"child support amount{i+1}": round((amt / twa) * ade, 2) if gross_pay > 0 else 0
                        for i, amt in enumerate(tcsa)
                    }
                    arrear_pool = wa - sum(tcsa)
                    total_arrears = sum(taa)
                    # Prorate arrear amounts
                    ar_amounts = {
                        f"arrear amount{i+1}": (
                            round((amt / total_arrears) * arrear_pool, 2)
                            if total_arrears and arrear_pool > 0 and gross_pay > 0 else 0
                        ) for i, amt in enumerate(taa)
                    }
                elif alloc_method == AllocationMethods.DEVIDEEQUALLY:
                    # Divide equally among orders
                    split_amt = round(ade / len(tcsa), 2) if tcsa else 0
                    cs_amounts = {
                        f"child support amount{i+1}": split_amt if gross_pay > 0 else 0
                        for i in range(len(tcsa))
                    }
                    arrear_pool = ade - sum(tcsa)
                    ar_amounts = {
                        f"arrear amount{i+1}": round(amt / len(taa), 2) if arrear_pool > 0 and gross_pay > 0 else 0
                        for i, amt in enumerate(taa)
                    }
                else:
                    import traceback as t
                    t.print_exc()
                    raise ValueError(
                        "Invalid allocation method for garnishment.")

            return {
                "result_amt": cs_amounts,
                "arrear_amt": ar_amounts,
                "ade": ade,
                "de": de,
                "mde": mandatory_deductions
            }
        except Exception as e:
            raise ValueError(f"Error in MultipleChild calculation: {str(e)}")
        

class ChildSupport(SingleChild, MultipleChild):
    """
    Main class to handle child support calculations.
    It can handle both single and multiple child support orders.
    """

    def calculate(self, record):
        try:
            garnishment_data = record.get('garnishment_data', [])
            ordered_amounts = self._support_amount(garnishment_data, CalculationFields.ORDERED_AMOUNT)
            if len(ordered_amounts) == 1:
                return SingleChild(self.work_state).calculate(record)
            else:
                return MultipleChild(self.work_state).calculate(record)
        except Exception as e:
           
            raise ValueError(f"Error in ChildSupport calculation: {str(e)}")