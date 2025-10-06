import re
from user_app.constants import FilingStatusFields as FS, EmployeeFields, CalculationFields
from datetime import datetime
from rest_framework.exceptions import APIException
import logging
import traceback as t
from decimal import Decimal


logger = logging.getLogger(__name__)


class FilingStatusFields:
    SINGLE = "single"
    MARRIED_FILING_JOINT_RETURN = "married_filing_joint_return"
    MARRIED_FILING_SEPARATE_RETURN = "married_filing_separate_return"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOWERS = "qualifying_widowers"
    ADDITIONAL_EXEMPT_AMOUNT = "additional_exempt_amount"
    ANY_OTHER_FILING_STATUS = "any_other_filing_status"


class FederalTaxCalculation:
    """
    Handles federal tax exemption calculations based on employee and spouse details.
    
    """

    def _get_year_from_date(self, date_string):
        if not date_string or len(date_string) < 4:
            raise ValueError("Invalid or missing date for year extraction.")
        try:
            return int(date_string[-4:])
        except ValueError:
            raise ValueError("Unable to parse year from date string.")

    def _normalize_filing_status(self, status):
        status = status.lower().strip()
        if status in {
            FilingStatusFields.QUALIFYING_WIDOWERS.lower(),
            FilingStatusFields.MARRIED_FILING_JOINT_RETURN.lower()
        }:
            return "married_filing_joint_return"
        return status

    # def _calculate_age_blind_exemptions(self, age, is_blind):
    #     return int(age >= 65) + int(is_blind)

    # def get_total_exemption_self(self, age,is_blind):
    #     return self._calculate_age_blind_exemptions(
    #         age,is_blind
    #     )

    # def get_total_exemption_dependent(self,spouse_age, is_spouse_blind):
    #     return self._calculate_age_blind_exemptions(
    #         spouse_age,is_spouse_blind)

    # def _get_additional_exempt_amount(self, pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, data, exemption_type='self'):
    #     try:
    #         year = str(self._get_year_from_date(statement_of_exemption_received_date))
    #         num_exemptions = (self.get_total_exemption_self(age, is_blind) if exemption_type == 'self'
    #                           else self.get_total_exemption_dependent(spouse_age,is_spouse_blind))

    #         normalized_status = self._normalize_filing_status(filing_status)

    #         federal_data = data.get('federal_add_exempt', [])


    #         for row in federal_data:
    #             if  row.get('filing_status').lower() in [normalized_status, FilingStatusFields.ANY_OTHER_FILING_STATUS.lower()]:
    #                 if (row.get('num_exemptions') == num_exemptions and
    #                     row.get('year') == str(year)):
    #                     amount = row.get(pay_period, 0)
    #                     return Decimal(str(amount)) if amount else Decimal('0.00')

    #         raise ValueError(f"No matching additional exemption data found for {exemption_type}.")

    #     except Exception as e:
    #         logger.error(f"Error in additional exemption ({exemption_type}): {e}\n{t.format_exc()}")
    #         raise ValueError(f"Failed to retrieve additional exemption amount for {exemption_type}: {e}")

    # def get_additional_exempt_for_self(self,pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data):
    #     return self._get_additional_exempt_amount(pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data, exemption_type='self')

    # def get_additional_exempt_for_dependent(self,pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data):
    #     return self._get_additional_exempt_amount(pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data, exemption_type='dependent')

    def get_standard_exempt_amt(self, filing_status,no_of_exemption_for_self,pay_period,statement_of_exemption_received_date, std_data):
        try:
            exemptions = no_of_exemption_for_self
            year = str(self._get_year_from_date(statement_of_exemption_received_date))

            normalized_status = self._normalize_filing_status(filing_status)
            exemptions_query = 6 if exemptions > 5 else exemptions
            
            for row in std_data:
                try:
                    row_exemptions = int(row.get('num_exemptions'))
                except (TypeError, ValueError):
                    continue
                
                if (row.get('filing_status').lower() == normalized_status and
                    row.get('payperiod', '').lower() == pay_period and str(row_exemptions) == str(exemptions_query) and
                    row.get('year') == str(year)):

                    raw_amount = row.get('exempt_amt')

                    if exemptions <= 5:
                        return Decimal(str(raw_amount))

                    # Parse formula like "56.15 plus 19.23 for each dependent"
                    nums = re.findall(r'\d+\.?\d*', str(raw_amount))
                    if len(nums) < 2:
                        raise ValueError(f"Invalid exemption formula: {raw_amount}")

                    base, extra = map(Decimal, nums[:2])
                    return round(base + extra * Decimal(exemptions), 2)

            raise ValueError(f"No matching standard exemption found for status '{filing_status}', period '{pay_period}', "
                             f"{exemptions} exemptions in year {year}.")

        except Exception as e:
            import traceback as t
            logger.error(f"Standard exemption calculation error: {e}\n{t.format_exc()}")
            raise ValueError(f"Failed to retrieve standard exemption amount: {e}")


class FederalTax(FederalTaxCalculation):
    def calculate(self, record, std_exempt_data):
        try:
            # Ensure types
            net_pay = Decimal(str(record.get(CalculationFields.NET_PAY, '0.00')))
            # age = record.get(EmployeeFields.AGE, 0)
            # is_blind = record.get(EmployeeFields.IS_BLIND, False)
            # spouse_age = record.get(EmployeeFields.SPOUSE_AGE, 0)
            # is_spouse_blind = record.get(EmployeeFields.IS_SPOUSE_BLIND, False)
            pay_period = record.get(EmployeeFields.PAY_PERIOD, "").lower()
            filing_status = record.get(EmployeeFields.FILING_STATUS, "").lower()
            no_of_exemption_for_self = record.get(EmployeeFields.NO_OF_EXEMPTION_INCLUDING_SELF)
            statement_of_exemption_received_date=(record.get(EmployeeFields.STATEMENT_OF_EXEMPTION_RECEIVED_DATE))

            if not record.get(EmployeeFields.STATEMENT_OF_EXEMPTION_RECEIVED_DATE):

                raise ValueError("Missing statement_of_exemption_received_date in record.")


            record[EmployeeFields.FILING_STATUS] = record.get(EmployeeFields.FILING_STATUS, "").lower()
            record[EmployeeFields.PAY_PERIOD] = record.get(EmployeeFields.PAY_PERIOD, "").lower()

            standard_amt = self.get_standard_exempt_amt(filing_status,no_of_exemption_for_self,pay_period,statement_of_exemption_received_date, std_exempt_data)
            # add_self = self.get_additional_exempt_for_self(pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data) if age >= 65 or is_blind else Decimal('0.00')
            # add_dep = self.get_additional_exempt_for_dependent(pay_period,filing_status,statement_of_exemption_received_date,age, is_blind,spouse_age,is_spouse_blind, add_exempt_data) if spouse_age >= 65 or is_spouse_blind else Decimal('0.00')
            total_exemption = standard_amt
            deduction = max(Decimal('0.00'), round(net_pay - total_exemption, 2))
            
            # Return proper dict structure for multiple garnishment compatibility
            return {
                "withholding_amt": deduction
            }

        except Exception as e:
            
            logger.error("Federal tax calculation failed: %s\n%s", str(e), t.format_exc())
            raise APIException(f"Federal tax calculation failed: {str(e)}")
