"""
Database operations service for garnishment calculations.
Handles all database-related operations including storing calculation results.
"""

import logging
from django.db import transaction
from typing import Dict, Any, List
from processor.models import (
    StateTaxLevyAppliedRule, StateTaxLevyConfig, CreditorDebtAppliedRule
)
from processor.serializers import StateTaxLevyConfigSerializers
from user_app.models import (
    EmployeeBatchData, GarnishmentBatchData, PayrollBatchData
)
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    GarnishmentDataKeys as GDK
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Service class for handling database operations related to garnishment calculations.
    """

    def __init__(self):
        self.logger = logger

    def process_and_store_case(self, case_info: Dict, batch_id: str, 
                              config_data: Dict, garn_fees: float = None) -> Dict:
        """
        Process and store garnishment case data in the database.
        """
        try:
            with transaction.atomic():
                ee_id = case_info.get(EE.EMPLOYEE_ID)
                state = self._get_state_name(case_info.get(EE.WORK_STATE))
                pay_period = case_info.get(EE.PAY_PERIOD).title()

                # Store employee data
                self._store_employee_data(case_info, ee_id)

                # Store payroll data
                self._store_payroll_data(case_info, ee_id)

                # Store garnishment data
                self._store_garnishment_data(case_info, ee_id)

                # Process garnishment rules
                self._process_garnishment_rules(case_info, state, pay_period, ee_id)

                return {"status": "success", "employee_id": ee_id}

        except Exception as e:
            self.logger.error(f"Error processing case for employee {case_info.get(EE.EMPLOYEE_ID)}: {e}")
            return {"error": f"Error processing case: {str(e)}"}

    def _get_state_name(self, work_state: str) -> str:
        """Get formatted state name."""
        from processor.garnishment_library.calculations import StateAbbreviations
        return StateAbbreviations(work_state).get_state_name_and_abbr().title()

    def _store_employee_data(self, case_info: Dict, ee_id: str) -> None:
        """Store employee batch data."""
        employee_defaults = {
            EE.CASE_ID: self._get_first_case_id(case_info),
            EE.WORK_STATE: case_info.get(EE.WORK_STATE),
            EE.NO_OF_EXEMPTION_INCLUDING_SELF: case_info.get(EE.NO_OF_EXEMPTION_INCLUDING_SELF),
            EE.PAY_PERIOD: case_info.get(EE.PAY_PERIOD),
            EE.FILING_STATUS: case_info.get(EE.FILING_STATUS),
            EE.AGE: case_info.get(EE.AGE),
            EE.IS_BLIND: case_info.get(EE.IS_BLIND),
            EE.IS_SPOUSE_BLIND: case_info.get(EE.IS_SPOUSE_BLIND),
            EE.SPOUSE_AGE: case_info.get(EE.SPOUSE_AGE),
            EE.SUPPORT_SECOND_FAMILY: case_info.get(EE.SUPPORT_SECOND_FAMILY),
            EE.NO_OF_STUDENT_DEFAULT_LOAN: case_info.get(EE.NO_OF_STUDENT_DEFAULT_LOAN),
            EE.ARREARS_GREATER_THAN_12_WEEKS: case_info.get(EE.ARREARS_GREATER_THAN_12_WEEKS),
            EE.NO_OF_DEPENDENT_EXEMPTION: case_info.get(EE.NO_OF_DEPENDENT_EXEMPTION),
        }
        
        EmployeeBatchData.objects.update_or_create(
            ee_id=ee_id, defaults=employee_defaults)

    def _store_payroll_data(self, case_info: Dict, ee_id: str) -> None:
        """Store payroll tax data."""
        payroll_data = case_info.get(PT.PAYROLL_TAXES, {})
        first_case_id = self._get_first_case_id(case_info)
        
        payroll_defaults = {
            CA.WAGES: case_info.get(CA.WAGES),
            CA.COMMISSION_AND_BONUS: case_info.get(CA.COMMISSION_AND_BONUS),
            CA.NON_ACCOUNTABLE_ALLOWANCES: case_info.get(CA.NON_ACCOUNTABLE_ALLOWANCES),
            CA.GROSS_PAY: case_info.get(CA.GROSS_PAY),
            EE.DEBT: case_info.get(EE.DEBT),
            EE.EXEMPTION_AMOUNT: case_info.get(EE.EXEMPTION_AMOUNT),
            CA.NET_PAY: case_info.get(CA.NET_PAY),
            PT.FEDERAL_INCOME_TAX: payroll_data.get(PT.FEDERAL_INCOME_TAX),
            PT.SOCIAL_SECURITY_TAX: payroll_data.get(PT.SOCIAL_SECURITY_TAX),
            PT.MEDICARE_TAX: payroll_data.get(PT.MEDICARE_TAX),
            PT.STATE_TAX: payroll_data.get(PT.STATE_TAX),
            PT.LOCAL_TAX: payroll_data.get(PT.LOCAL_TAX),
            PT.UNION_DUES: payroll_data.get(PT.UNION_DUES),
            PT.MEDICAL_INSURANCE_PRETAX: payroll_data.get(PT.MEDICAL_INSURANCE_PRETAX),
            PT.INDUSTRIAL_INSURANCE: payroll_data.get(PT.INDUSTRIAL_INSURANCE),
            PT.LIFE_INSURANCE: payroll_data.get(PT.LIFE_INSURANCE),
            PT.CALIFORNIA_SDI: payroll_data.get(PT.CALIFORNIA_SDI, 0),
        }

        PayrollBatchData.objects.update_or_create(
            case_id=first_case_id, defaults={**payroll_defaults, "ee_id": ee_id})

    def _store_garnishment_data(self, case_info: Dict, ee_id: str) -> None:
        """Store garnishment batch data."""
        unique_garnishments_to_create = {}
        
        for garnishment_group in case_info.get(CA.GARNISHMENT_DATA, []):
            garnishment_type = garnishment_group.get(
                EE.GARNISHMENT_TYPE, garnishment_group.get(GDK.TYPE, ""))
            
            for garnishment in garnishment_group.get(GDK.DATA, []):
                case_id_garnish = garnishment.get(EE.CASE_ID)
                if case_id_garnish:
                    unique_garnishments_to_create[case_id_garnish] = GarnishmentBatchData(
                        case_id=case_id_garnish,
                        garnishment_type=garnishment_type,
                        ordered_amount=garnishment.get(CA.ORDERED_AMOUNT),
                        arrear_amount=garnishment.get(CA.ARREAR_AMOUNT),
                        current_medical_support=garnishment.get(CA.CURRENT_MEDICAL_SUPPORT),
                        past_due_medical_support=garnishment.get(CA.PAST_DUE_MEDICAL_SUPPORT),
                        current_spousal_support=garnishment.get(CA.CURRENT_SPOUSAL_SUPPORT),
                        past_due_spousal_support=garnishment.get(CA.PAST_DUE_SPOUSAL_SUPPORT),
                        ee_id=ee_id
                    )

        if unique_garnishments_to_create:
            GarnishmentBatchData.objects.bulk_create(
                unique_garnishments_to_create.values(),
                update_conflicts=True,
                unique_fields=["case_id"],
                update_fields=[
                    "garnishment_type", "ordered_amount", "arrear_amount",
                    "current_medical_support", "past_due_medical_support",
                    "current_spousal_support", "past_due_spousal_support", "ee_id"
                ]
            )

    def _process_garnishment_rules(self, case_info: Dict, state: str, 
                                  pay_period: str, ee_id: str) -> None:
        """Process and store garnishment rules."""
        garnishment_type_data = case_info.get(EE.GARNISHMENT_DATA)
        
        if garnishment_type_data:
            for garnishment_group in garnishment_type_data:
                garnishment_type = garnishment_group.get(GDK.TYPE, "").lower()
                garnishment_data_list = garnishment_group.get(GDK.DATA, [])
                
                for garnishment_item in garnishment_data_list:
                    case_id = garnishment_item.get(EE.CASE_ID, 0)
                    
                    if garnishment_type == GT.STATE_TAX_LEVY.lower():
                        self._process_state_tax_levy_rule(state, case_id, ee_id, pay_period)
                    elif garnishment_type == GT.CREDITOR_DEBT.lower():
                        self._process_creditor_debt_rule(case_id, ee_id, state, pay_period)

    def _process_state_tax_levy_rule(self, state: str, case_id: int, 
                                   ee_id: str, pay_period: str) -> None:
        """Process state tax levy rules."""
        try:
            rule = StateTaxLevyConfig.objects.get(state__iexact=state)
            serializer_data = StateTaxLevyConfigSerializers(rule).data
            serializer_data.update({
                CR.WITHHOLDING_BASIS: None,  # Will be updated by calculation
                CR.WITHHOLDING_CAP: None,    # Will be updated by calculation
                EE.EMPLOYEE_ID: ee_id,
                EE.PAY_PERIOD: pay_period
            })
            serializer_data.pop('id', None)
            StateTaxLevyAppliedRule.objects.update_or_create(
                case_id=case_id, defaults=serializer_data)
        except StateTaxLevyConfig.DoesNotExist:
            self.logger.warning(f"State tax levy config not found for state: {state}")

    def _process_creditor_debt_rule(self, case_id: int, ee_id: str, 
                                  state: str, pay_period: str) -> None:
        """Process creditor debt rules."""
        data = {
            EE.EMPLOYEE_ID: ee_id,
            CR.WITHHOLDING_BASIS: None,  # Will be updated by calculation
            EE.STATE: state,
            CR.WITHHOLDING_CAP: None,    # Will be updated by calculation
            EE.PAY_PERIOD: pay_period
        }
        CreditorDebtAppliedRule.objects.update_or_create(
            case_id=case_id, defaults=data)

    def _get_first_case_id(self, case_info: Dict) -> int:
        """Get the first case ID from garnishment data."""
        first_case_id = 0
        if case_info.get(EE.GARNISHMENT_DATA):
            first_group = case_info.get(EE.GARNISHMENT_DATA, [{}])[0]
            first_case_data = first_group.get(GDK.DATA, [{}])
            if first_case_data:
                first_case_id = first_case_data[0].get(EE.CASE_ID, 0)
        return first_case_id

    def update_calculation_results(self, case_id: int, result: Dict) -> None:
        """Update calculation results in the database."""
        try:
            # Update withholding basis and cap if present
            withholding_basis = result.get(CR.WITHHOLDING_BASIS)
            withholding_cap = result.get(CR.WITHHOLDING_CAP)
            
            if withholding_basis is not None or withholding_cap is not None:
                # Update state tax levy rules if applicable
                StateTaxLevyAppliedRule.objects.filter(case_id=case_id).update(
                    **{k: v for k, v in {
                        CR.WITHHOLDING_BASIS: withholding_basis,
                        CR.WITHHOLDING_CAP: withholding_cap
                    }.items() if v is not None}
                )
                
                # Update creditor debt rules if applicable
                CreditorDebtAppliedRule.objects.filter(case_id=case_id).update(
                    **{k: v for k, v in {
                        CR.WITHHOLDING_BASIS: withholding_basis,
                        CR.WITHHOLDING_CAP: withholding_cap
                    }.items() if v is not None}
                )
                
        except Exception as e:
            self.logger.error(f"Error updating calculation results for case {case_id}: {e}")

    def get_employee_batch_data(self, ee_id: str) -> Dict:
        """Get employee batch data by employee ID."""
        try:
            employee = EmployeeBatchData.objects.get(ee_id=ee_id)
            return {
                'ee_id': employee.ee_id,
                'work_state': employee.work_state,
                'pay_period': employee.pay_period,
                'filing_status': employee.filing_status,
                'age': employee.age,
                'is_blind': employee.is_blind,
                'is_spouse_blind': employee.is_spouse_blind,
                'spouse_age': employee.spouse_age,
                'support_second_family': employee.support_second_family,
                'no_of_student_default_loan': employee.no_of_student_default_loan,
                'arrears_greater_than_12_weeks': employee.arrears_greater_than_12_weeks,
                'no_of_dependent_exemption': employee.no_of_dependent_exemption,
            }
        except EmployeeBatchData.DoesNotExist:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting employee batch data for {ee_id}: {e}")
            return {}

    def get_payroll_batch_data(self, case_id: int) -> Dict:
        """Get payroll batch data by case ID."""
        try:
            payroll = PayrollBatchData.objects.get(case_id=case_id)
            return {
                'case_id': payroll.case_id,
                'ee_id': payroll.ee_id,
                'wages': payroll.wages,
                'commission_and_bonus': payroll.commission_and_bonus,
                'non_accountable_allowances': payroll.non_accountable_allowances,
                'gross_pay': payroll.gross_pay,
                'debt': payroll.debt,
                'exemption_amount': payroll.exemption_amount,
                'net_pay': payroll.net_pay,
                'federal_income_tax': payroll.federal_income_tax,
                'social_security_tax': payroll.social_security_tax,
                'medicare_tax': payroll.medicare_tax,
                'state_tax': payroll.state_tax,
                'local_tax': payroll.local_tax,
                'union_dues': payroll.union_dues,
                'medical_insurance_pretax': payroll.medical_insurance_pretax,
                'industrial_insurance': payroll.industrial_insurance,
                'life_insurance': payroll.life_insurance,
                'california_sdi': payroll.california_sdi,
            }
        except PayrollBatchData.DoesNotExist:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting payroll batch data for case {case_id}: {e}")
            return {}

    def get_garnishment_batch_data(self, case_id: int) -> Dict:
        """Get garnishment batch data by case ID."""
        try:
            garnishment = GarnishmentBatchData.objects.get(case_id=case_id)
            return {
                'case_id': garnishment.case_id,
                'garnishment_type': garnishment.garnishment_type,
                'ordered_amount': garnishment.ordered_amount,
                'arrear_amount': garnishment.arrear_amount,
                'current_medical_support': garnishment.current_medical_support,
                'past_due_medical_support': garnishment.past_due_medical_support,
                'current_spousal_support': garnishment.current_spousal_support,
                'past_due_spousal_support': garnishment.past_due_spousal_support,
                'ee_id': garnishment.ee_id,
            }
        except GarnishmentBatchData.DoesNotExist:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting garnishment batch data for case {case_id}: {e}")
            return {}
