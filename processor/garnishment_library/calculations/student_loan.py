from rest_framework import status
from rest_framework.response import Response
from .child_support import ChildSupportHelper
from processor.garnishment_library.utils import ExemptAmount
from user_app.constants import (
    EmployeeFields as EE,
    CalculationFields as CF,
    PayrollTaxesFields as PT,
    PayPeriodFields as PP
)
import traceback as t
import logging

logger = logging.getLogger(__name__)

#Configure Details
DE_LOWER_LIMIT_PERCENTAGE = 0.10
DE_MID_LIMIT_PERCENTAGE = 0.15
DE_UPPER_LIMIT_PERCENTAGE = 0.25


class StudentLoan:
    """
    Handles calculation of Student Loan garnishment amounts based on federal and state rules.
    """

    def _calculate_disposable_earnings(self,work_state, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes):
        """
        Calculates disposable earnings by subtracting mandatory deductions from gross pay.
        """
        cs_helper = ChildSupportHelper(work_state)
        gross_pay = cs_helper.calculate_gross_pay(wages, commission_and_bonus, non_accountable_allowances)
        mandatory_deductions = cs_helper.calculate_md(payroll_taxes)
        disposable_earnings = cs_helper.calculate_de(gross_pay, mandatory_deductions)

        return disposable_earnings

    def get_single_student_amount(self, work_state,pay_period, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes):
        """
        Calculates the garnishment amount for a single student loan.
        """
        try:
            de =  self._calculate_disposable_earnings(work_state, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes)
            fmw = ExemptAmount().get_fmw(pay_period)

            if de <= fmw:
                return {
                    "student_loan_amt": "Student loan withholding cannot be applied because Disposable Earnings are less than or equal to the exempt amount."
                }

            deduction = min(de * DE_MID_LIMIT_PERCENTAGE, de *DE_UPPER_LIMIT_PERCENTAGE, de - fmw)
            return {"student_loan_amt": {"student_loan_amt1": round(deduction, 2)}, "disposable_earning": de}

        except Exception as e:
            return {
                "student_loan_amt": {"student_loan_amt1": f"Error calculating single student loan amount: {e}"},"disposable_earning": 0
            }

    def get_multiple_student_amount(self, work_state,pay_period, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes):
        """
        Calculates the garnishment amounts for multiple student loans.
        """
        try:
            
            de = self._calculate_disposable_earnings(work_state, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes)
            fmw = ExemptAmount().get_fmw(pay_period)
      
            if de <= fmw:
                msg = "Student loan withholding cannot be applied because Disposable Earnings are less than or equal to the exempt amount."
                return {"student_loan_amt": {"student_loan_amt1": msg, "student_loan_amt2": msg}, "disposable_earning": de}

            return {"student_loan_amt": {"student_loan_amt1": round(de * DE_MID_LIMIT_PERCENTAGE, 2),
                                         "student_loan_amt2": round(de * DE_LOWER_LIMIT_PERCENTAGE, 2)}, "disposable_earning": de}

        except Exception as e:
            return {"student_loan_amt": {
                "student_loan_amt1": f"Error calculating multiple student loan amount: {e}",
                "student_loan_amt2": f"Error calculating multiple student loan amount: {e}"
            }, "disposable_earning": de}


class StudentLoanCalculator:
    """
    Service to calculate student loan garnishment for single or multiple cases.
    """

    def calculate(self, record):
        """
        Determines and calculates the appropriate student loan garnishment amount(s).
        Returns a DRF Response object on error.
        """
        try:

            state_name = record.get(EE.WORK_STATE).strip().upper()
            wages = record.get(CF.WAGES, 0)
            commission_and_bonus = record.get(CF.COMMISSION_AND_BONUS, 0)
            pay_period = record.get(EE.PAY_PERIOD.lower()).strip().lower()
            non_accountable_allowances = record.get(CF.NON_ACCOUNTABLE_ALLOWANCES, 0)
            payroll_taxes = record.get(PT.PAYROLL_TAXES, {})


            count = record.get(EE.NO_OF_STUDENT_DEFAULT_LOAN)
            student_loan = StudentLoan()

            if count == 1:
                return student_loan.get_single_student_amount(state_name,pay_period, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes)
            elif count and count > 1:
                return student_loan.get_multiple_student_amount(state_name,pay_period, wages,commission_and_bonus,non_accountable_allowances,payroll_taxes)
            else:
                return {"student_loan_amt": {"student_loan_amt1": 0}, "disposable_earning": 0}

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
