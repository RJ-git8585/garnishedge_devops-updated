"""
Database operations service for garnishment calculations.
Handles all database-related operations including storing calculation results.
"""

import logging
from django.db import transaction
from typing import Dict, Any, List
from datetime import datetime
from processor.models import (
    StateTaxLevyAppliedRule, StateTaxLevyConfig, CreditorDebtAppliedRule
)
from processor.models.garnishment_result.result import GarnishmentResult
from processor.models.shared_model.garnishment_type import GarnishmentType
from processor.models.shared_model.state import State
from processor.serializers import StateTaxLevyConfigSerializers
from user_app.models import (
    EmployeeBatchData, GarnishmentBatchData, PayrollBatchData
)
from user_app.models.employee.employee_details import EmployeeDetail
from user_app.models.garnishment_order.garnishment_orders import GarnishmentOrder
from user_app.models.payroll.payroll import Payroll
from user_app.models.client.client_models import Client
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    GarnishmentDataKeys as GDK,
    GarnishmentResultFields as GRF
)
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Service class for handling database operations related to garnishment calculations.
    """

    def __init__(self):
        self.logger = logger

    def process_and_store_case(self, case_info: Dict, batch_id: str, 
                              config_data: Dict,result:Dict, garn_fees: float = None) -> Dict:
        """
        Process and store garnishment case data in the database.
        """
        try:
            with transaction.atomic():
                ee_id = case_info.get(EE.EMPLOYEE_ID)
                state = self._get_state_name(case_info.get(EE.WORK_STATE))
                pay_period = case_info.get(EE.PAY_PERIOD).title()


                # # Store payroll data
                # self._store_payroll_data(case_info, ee_id)

                self._store_garnishment_results(case_info, ee_id, batch_id, result)

                # Store garnishment data (result will be passed separately if available)
                # Note: result parameter is optional and can be passed later via update_calculation_results

                # # Process garnishment rules
                # self._process_garnishment_rules(case_info, state, pay_period, ee_id)

                return {"status": "success", "employee_id": ee_id}

        except Exception as e:
            self.logger.error(f"Error processing case for employee {case_info.get(EE.EMPLOYEE_ID)}: {e}")
            return {"error": f"Error processing case: {str(e)}"}

    def _process_garnishment_rules(self, case_info: Dict, state: str, pay_period: str, ee_id: str) -> None:
        """
        Process and store garnishment rules.
        This is a placeholder method - implement as needed.
        """
        # TODO: Implement garnishment rules processing if needed
        pass

    def _get_state_name(self, work_state: str) -> str:
        """Get formatted state name."""
        from processor.garnishment_library.calculations import StateAbbreviations
        return StateAbbreviations(work_state).get_state_name_and_abbr().title()


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


    def _get_first_case_id(self, case_info: Dict) -> int:
        """Get the first case ID from garnishment data."""
        first_case_id = 0
        if case_info.get(EE.GARNISHMENT_DATA):
            first_group = case_info.get(EE.GARNISHMENT_DATA, [{}])[0]
            first_case_data = first_group.get(GDK.DATA, [{}])
            if first_case_data:
                first_case_id = first_case_data[0].get(EE.CASE_ID, 0)
        return first_case_id

    def _store_garnishment_results(self, case_info: Dict, ee_id: str, batch_id: str = None, result: Dict = None) -> None:
        """Store calculation results in the GarnishmentResult table."""
        try:
            if not result:
                self.logger.warning(f"No result data provided for employee {ee_id}")
                return

            # Extract basic information from result

            calculation_status = result.get(GRF.CALCULATION_STATUS)
            garnishment_details = result.get(GRF.GARNISHMENT_DETAILS, [])
            calculation_metrics = result.get(GRF.CALCULATION_METRICS, {})
            er_deductions = result.get(CR.ER_DEDUCTION, {})

            # Extract calculation metrics
            disposable_earnings = calculation_metrics.get(GRF.DISPOSABLE_EARNINGS)
            total_mandatory_deductions = calculation_metrics.get(GRF.TOTAL_MANDATORY_DEDUCTIONS)
            allowable_disposable_earnings = calculation_metrics.get(GRF.ALLOWABLE_DISPOSABLE_EARNINGS)
            withholding_limit = calculation_metrics.get(GRF.WITHHOLDING_LIMIT)
           
            # Extract garnishment fees (from ER_DEDUCTION, which is shared across all garnishments)
            garnishment_fees_note = er_deductions.get(GRF.GARNISHMENT_FEES, "No Provision")
            
            # Handle garnishment_details as a list (new structure)
            # For single garnishments: list with one item
            # For multiple garnishments: list with multiple items
            if not isinstance(garnishment_details, list):
                self.logger.error(f"garnishment_details is not a list for employee {ee_id}")
                return
            
            if not garnishment_details:
                self.logger.warning(f"No garnishment details found for employee {ee_id}")
                return
            
            # Process each garnishment detail in the list
            for garnishment_detail in garnishment_details:
                # Extract garnishment type from the detail (moved inside each item)
                garnishment_type = garnishment_detail.get(GRF.GARNISHMENT_TYPE)
                
                # Extract garnishment details from this item
                withholding_amounts = garnishment_detail.get(GRF.WITHHOLDING_AMOUNTS, [])
                arrear_amounts = garnishment_detail.get(GRF.ARREAR_AMOUNTS, [])
                total_withheld = garnishment_detail.get(GRF.TOTAL_WITHHELD)
                net_withholding = garnishment_detail.get(GRF.NET_WITHHOLDING)
                
                # Extract withholding basis, cap, and limit rule from this garnishment detail
                withholding_basis = garnishment_detail.get(GRF.WITHHOLDING_BASIS)
                withholding_cap = garnishment_detail.get(GRF.WITHHOLDING_CAP)   
                
                # For multiple garnishments, each item may have its own garnishment_fees
                # Otherwise use the shared one from er_deductions
                detail_garnishment_fees = garnishment_detail.get(GRF.GARNISHMENT_FEES)
                if detail_garnishment_fees is not None:
                    garnishment_fees_note = detail_garnishment_fees

                # Get payroll data for gross_pay and net_pay
                gross_pay = case_info.get(CA.GROSS_PAY)
                net_pay = case_info.get(CA.NET_PAY)

                # Look up EmployeeDetail by ee_id
                try:
                    employee = EmployeeDetail.objects.get(ee_id=ee_id)
                except EmployeeDetail.DoesNotExist:
                    self.logger.error(f"EmployeeDetail not found for ee_id: {ee_id}")
                    continue
                except EmployeeDetail.MultipleObjectsReturned:
                    self.logger.warning(f"Multiple EmployeeDetail found for ee_id: {ee_id}, using first")
                    employee = EmployeeDetail.objects.filter(ee_id=ee_id).first()

                # Look up GarnishmentType by type
                garnishment_type_obj = None
                if garnishment_type:
                    try:
                        garnishment_type_obj = GarnishmentType.objects.get(type__iexact=garnishment_type)
                    except GarnishmentType.DoesNotExist:
                        self.logger.error(f"GarnishmentType not found for type: {garnishment_type}. Skipping this garnishment detail.")
                        continue
                    except GarnishmentType.MultipleObjectsReturned:
                        self.logger.warning(f"Multiple GarnishmentType found for type: {garnishment_type}, using first")
                        garnishment_type_obj = GarnishmentType.objects.filter(type__iexact=garnishment_type).first()
                else:
                    self.logger.error(f"No garnishment_type provided in garnishment detail. Skipping this detail.")
                    continue

                # Handle multiple withholding amounts - create one record per case_id
                if withholding_amounts:
                    # Group by case_id if available
                    case_withholdings = {}
                    for withholding in withholding_amounts:
                        case_id = withholding.get(GRF.CASE_ID)
                        amount = withholding.get(GRF.AMOUNT, 0)
                        if isinstance(amount, str) and amount.lower() in [GRF.INSUFFICIENT_PAY, "insufficient_pay"]:
                            amount = 0
                        
                        if case_id:
                            if case_id not in case_withholdings:
                                case_withholdings[case_id] = {
                                    'withholding_amount': 0,
                                    'withholding_arrear': 0
                                }
                            case_withholdings[case_id]['withholding_amount'] += float(amount) if amount else 0
                        else:
                            # If no case_id, use a default or create a single record
                            default_case_id = "unknown"
                            if default_case_id not in case_withholdings:
                                case_withholdings[default_case_id] = {
                                    'withholding_amount': 0,
                                    'withholding_arrear': 0
                                }
                            case_withholdings[default_case_id]['withholding_amount'] += float(amount) if amount else 0

                    # Process arrear amounts
                    for arrear in arrear_amounts:
                        case_id = arrear.get(GRF.CASE_ID)
                        amount = arrear.get(GRF.AMOUNT, 0)
                        if isinstance(amount, str) and amount.lower() in [GRF.INSUFFICIENT_PAY, "insufficient_pay"]:
                            amount = 0
                        
                        if case_id and case_id in case_withholdings:
                            case_withholdings[case_id]['withholding_arrear'] += float(amount) if amount else 0
                        elif case_id:
                            case_withholdings[case_id] = {
                                'withholding_amount': 0,
                                'withholding_arrear': float(amount) if amount else 0
                            }

                    # Create records for each case
                    for case_id_str, amounts in case_withholdings.items():
                        # Get ordered_amount and arrear_amount from case_info if available
                        ordered_amount = None
                        arrear_amount = None
                        garnishment_order_obj = None
                        
                        # Look up GarnishmentOrder by case_id if it's not "unknown"
                        if case_id_str != "unknown":
                            try:
                                garnishment_order_obj = GarnishmentOrder.objects.get(case_id=str(case_id_str))
                                # Get ordered_amount and arrear_amount from the order if available
                                ordered_amount = garnishment_order_obj.ordered_amount
                                arrear_amount = garnishment_order_obj.arrear_amount
                            except GarnishmentOrder.DoesNotExist:
                                self.logger.warning(f"GarnishmentOrder not found for case_id: {case_id_str}. Skipping record creation.")
                                continue
                            except GarnishmentOrder.MultipleObjectsReturned:
                                self.logger.warning(f"Multiple GarnishmentOrder found for case_id: {case_id_str}, using first")
                                garnishment_order_obj = GarnishmentOrder.objects.filter(case_id=str(case_id_str)).first()
                                if garnishment_order_obj:
                                    ordered_amount = garnishment_order_obj.ordered_amount
                                    arrear_amount = garnishment_order_obj.arrear_amount
                                else:
                                    self.logger.warning(f"Could not retrieve GarnishmentOrder for case_id: {case_id_str}. Skipping record creation.")
                                    continue
                        else:
                            # If case_id is "unknown", we can't create a record since case_id is required
                            self.logger.warning(f"case_id is 'unknown' for employee {ee_id}. Skipping record creation as case_id is required.")
                            continue
                        
                        # If not found in order, try to extract from garnishment data
                        if ordered_amount is None and case_info.get(EE.GARNISHMENT_DATA):
                            for group in case_info.get(EE.GARNISHMENT_DATA, []):
                                for case_data in group.get(GDK.DATA, []):
                                    if str(case_data.get(EE.CASE_ID)) == str(case_id_str):
                                        ordered_amount = case_data.get("ordered_amount", 0)
                                        arrear_amount = case_data.get("arrear_amount", 0)
                                        break

                        result_data = {
                            'batch_id': batch_id or 'unknown',
                            'ee': employee,
                            'case': garnishment_order_obj,
                            'gross_pay': gross_pay,
                            'net_pay': net_pay,
                            'total_mandatory_deduction': total_mandatory_deductions,
                            'disposable_earning': disposable_earnings,
                            'allowable_disposable_earning': allowable_disposable_earnings,
                            'ordered_amount': ordered_amount,
                            'arrear_amount': arrear_amount,
                            'withholding_amount': amounts.get('withholding_amount'),
                            'withholding_arrear': amounts.get('withholding_arrear'),
                            'garnishment_type': garnishment_type_obj,
                            'withholding_limit': withholding_limit,
                            'withholding_basis': withholding_basis,
                            'withholding_cap': withholding_cap,
                            'garnishment_fees_note': str(garnishment_fees_note) if garnishment_fees_note else None,
                            'processed_at': timezone.now()
                        }

                        # Create new GarnishmentResult record
                        GarnishmentResult.objects.create(**result_data)

                else:
                    # No withholding amounts - try to find a case_id from garnishment data
                    # Since case_id is required, we need to find a GarnishmentOrder
                    garnishment_order_obj = None
                    ordered_amount = None
                    arrear_amount = None
                    
                    # Try to get case_id from garnishment data
                    if case_info.get(EE.GARNISHMENT_DATA):
                        for group in case_info.get(EE.GARNISHMENT_DATA, []):
                            for case_data in group.get(GDK.DATA, []):
                                case_id_str = case_data.get(EE.CASE_ID)
                                if case_id_str:
                                    try:
                                        garnishment_order_obj = GarnishmentOrder.objects.get(case_id=str(case_id_str))
                                        ordered_amount = garnishment_order_obj.ordered_amount
                                        arrear_amount = garnishment_order_obj.arrear_amount
                                        break
                                    except GarnishmentOrder.DoesNotExist:
                                        continue
                                    except GarnishmentOrder.MultipleObjectsReturned:
                                        garnishment_order_obj = GarnishmentOrder.objects.filter(case_id=str(case_id_str)).first()
                                        if garnishment_order_obj:
                                            ordered_amount = garnishment_order_obj.ordered_amount
                                            arrear_amount = garnishment_order_obj.arrear_amount
                                        break
                    
                    if not garnishment_order_obj:
                        self.logger.warning(f"No GarnishmentOrder found for employee {ee_id} with no withholding amounts for garnishment type {garnishment_type}. Skipping this garnishment detail.")
                        continue
                    
                    # Create a single record with aggregated data
                    result_data = {
                        'batch_id': batch_id or 'unknown',
                        'ee': employee,
                        'case': garnishment_order_obj,
                        'gross_pay': gross_pay,
                        'net_pay': net_pay,
                        'total_mandatory_deduction': total_mandatory_deductions,
                        'disposable_earning': disposable_earnings,
                        'allowable_disposable_earning': allowable_disposable_earnings,
                        'withholding_amount': total_withheld,
                        'withholding_arrear': sum(float(a.get(GRF.AMOUNT, 0)) for a in arrear_amounts if not isinstance(a.get(GRF.AMOUNT), str)),
                        'garnishment_type': garnishment_type_obj,
                        'withholding_limit': withholding_limit,
                        'withholding_basis': withholding_basis,
                        'withholding_cap': withholding_cap,
                        'garnishment_fees_note': str(garnishment_fees_note) if garnishment_fees_note else None,
                        'processed_at': timezone.now()
                    }

                    # Create new GarnishmentResult record
                    GarnishmentResult.objects.create(**result_data)


        except Exception as e:
            self.logger.error(f"Error storing garnishment results for employee {ee_id}: {e}", exc_info=True)

    def update_calculation_results(self, case_id: int, result: Dict, batch_id: str = None, case_info: Dict = None) -> None:
        """
        Update calculation results in the database.
        This is a public method that extracts case_info and calls _store_garnishment_results.
        
        Args:
            case_id: The case ID
            result: The calculation result dictionary
            batch_id: Optional batch ID (will be extracted from payroll data if not provided)
            case_info: Optional case info dictionary (will be built from payroll data if not provided)
        """
        try:
            # Extract employee_id from result
            ee_id = result.get(GRF.EMPLOYEE_ID)
            if not ee_id:
                self.logger.warning(f"No employee_id found in result for case {case_id}")
                return

            # If case_info is not provided, try to build it from PayrollBatchData
            if not case_info:
                try:
                    payroll_data = PayrollBatchData.objects.get(case_id=case_id)
                    if not batch_id:
                        batch_id = getattr(payroll_data, 'batch_id', None) if hasattr(payroll_data, 'batch_id') else None
                    # Build a minimal case_info dict with necessary fields
                    case_info = {
                        EE.EMPLOYEE_ID: payroll_data.ee_id,
                        CA.GROSS_PAY: payroll_data.gross_pay,
                        CA.NET_PAY: payroll_data.net_pay,
                        EE.GARNISHMENT_DATA: []  # Will be populated if needed
                    }
                except PayrollBatchData.DoesNotExist:
                    # If payroll data doesn't exist, create minimal case_info
                    case_info = {
                        EE.EMPLOYEE_ID: ee_id,
                        CA.GROSS_PAY: result.get(GRF.CALCULATION_METRICS, {}).get('gross_pay'),
                        CA.NET_PAY: None,
                        EE.GARNISHMENT_DATA: []
                    }
                    if not batch_id:
                        batch_id = None

            # Call the internal method to store results
            self._store_garnishment_results(case_info, ee_id, batch_id, result)

        except Exception as e:
            self.logger.error(f"Error updating calculation results for case {case_id}: {e}", exc_info=True)

    def _store_payroll_batch_data(self, case_id: int) -> Dict:
        """Store payroll batch data by case ID."""
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

    def store_payroll_data(self, payroll_json: Dict) -> Dict:
        """
        Store payroll data from JSON structure to Payroll database table.
        
        Args:
            payroll_json: Dictionary containing batch_id and payroll_data array
                Example:
                {
                    "batch_id": "BLUR449",
                    "payroll_data": [
                        {
                            "client_id": "CLT10009",
                            "ee_id": "DA0075",
                            "pay_period": "Weekly",
                            "payroll_date": "2025-10-31T00:00:00",
                            "wages": 400,
                            "commission_and_bonus": 0,
                            "non_accountable_allowances": 100,
                            "gross_pay": 500,
                            "payroll_taxes": {
                                "federal_income_tax": 100,
                                "state_tax": 0,
                                "local_tax": 0,
                                "medicare_tax": 0,
                                "social_security_tax": 0,
                                "wilmington_tax": 0,
                                "california_sdi": 0,
                                "medical_insurance_pretax": 0,
                                "life_insurance": 0,
                                "retirement_401k": 0,
                                "industrial_insurance": 0,
                                "union_dues": 0
                            },
                            "net_pay": 400,
                            "pay_date": "2025-11-20"
                        }
                    ]
                }
        
        Returns:
            Dict with status and details of stored records
        """
        try:
            batch_id = payroll_json.get("batch_id")
            payroll_data_list = payroll_json.get("payroll_data", [])
            
            if not payroll_data_list:
                return {"status": "error", "message": "No payroll_data found in JSON"}
            
            stored_records = []
            errors = []
            
            with transaction.atomic():
                for payroll_item in payroll_data_list:
                    try:
                        # Extract basic fields
                        client_id = payroll_item.get("client_id")
                        ee_id = payroll_item.get("ee_id")
                        pay_period = payroll_item.get("pay_period")
                        payroll_date_str = payroll_item.get("payroll_date")
                        pay_date_str = payroll_item.get("pay_date")
                        
                        # Validate required fields
                        if not client_id or not ee_id:
                            errors.append(f"Missing required fields (client_id or ee_id) for payroll item")
                            continue
                        
                        if not payroll_date_str:
                            errors.append(f"Missing required field payroll_date for ee_id {ee_id}")
                            continue
                        
                        # Get Client
                        try:
                            client = Client.objects.get(client_id=client_id)
                        except Client.DoesNotExist:
                            errors.append(f"Client with client_id '{client_id}' not found")
                            continue
                        except Client.MultipleObjectsReturned:
                            self.logger.warning(f"Multiple clients found for client_id '{client_id}', using first")
                            client = Client.objects.filter(client_id=client_id).first()
                        
                        # Get EmployeeDetail
                        try:
                            employee = EmployeeDetail.objects.get(ee_id=ee_id)
                        except EmployeeDetail.DoesNotExist:
                            errors.append(f"Employee with ee_id '{ee_id}' not found")
                            continue
                        except EmployeeDetail.MultipleObjectsReturned:
                            self.logger.warning(f"Multiple employees found for ee_id '{ee_id}', using first")
                            employee = EmployeeDetail.objects.filter(ee_id=ee_id).first()
                        
                        # Get State from employee's work_state
                        state = employee.work_state
                        if not state:
                            errors.append(f"Employee {ee_id} does not have a work_state")
                            continue
                        
                        # Parse dates
                        payroll_date = None
                        if payroll_date_str:
                            try:
                                # Handle ISO format with time (2025-10-31T00:00:00)
                                if 'T' in payroll_date_str:
                                    payroll_date = datetime.fromisoformat(payroll_date_str.replace('Z', '+00:00')).date()
                                else:
                                    payroll_date = datetime.strptime(payroll_date_str, "%Y-%m-%d").date()
                            except (ValueError, AttributeError) as e:
                                self.logger.error(f"Error parsing payroll_date '{payroll_date_str}': {e}")
                                errors.append(f"Invalid payroll_date format: {payroll_date_str}")
                                continue
                        
                        pay_date = None
                        if pay_date_str:
                            try:
                                # Handle ISO format with time or simple date
                                if 'T' in pay_date_str:
                                    pay_date = datetime.fromisoformat(pay_date_str.replace('Z', '+00:00')).date()
                                else:
                                    pay_date = datetime.strptime(pay_date_str, "%Y-%m-%d").date()
                            except (ValueError, AttributeError) as e:
                                self.logger.error(f"Error parsing pay_date '{pay_date_str}': {e}")
                                # pay_date is optional, so we'll just log and continue
                        
                        # Extract payroll_taxes
                        payroll_taxes = payroll_item.get("payroll_taxes", {})
                        
                        # Prepare payroll data
                        payroll_defaults = {
                            'state': state,
                            'ee_id': employee,
                            'client_id': client,
                            'batch_id': batch_id,
                            'pay_period': pay_period,
                            'payroll_date': payroll_date,
                            'pay_date': pay_date,
                            'wages': payroll_item.get("wages"),
                            'commission_and_bonus': payroll_item.get("commission_and_bonus"),
                            'non_accountable_allowances': payroll_item.get("non_accountable_allowances"),
                            'gross_pay': payroll_item.get("gross_pay"),
                            'net_pay': payroll_item.get("net_pay"),
                            'federal_income_tax': payroll_taxes.get("federal_income_tax"),
                            'state_tax': payroll_taxes.get("state_tax"),
                            'local_tax': payroll_taxes.get("local_tax"),
                            'medicare_tax': payroll_taxes.get("medicare_tax"),
                            'social_security_tax': payroll_taxes.get("social_security_tax"),
                            'wilmington_tax': payroll_taxes.get("wilmington_tax"),
                            'california_sdi': payroll_taxes.get("california_sdi"),
                            'medical_insurance_pretax': payroll_taxes.get("medical_insurance_pretax"),
                            'life_insurance': payroll_taxes.get("life_insurance"),
                            'retirement_401k': payroll_taxes.get("retirement_401k"),
                            'industrial_insurance': payroll_taxes.get("industrial_insurance"),
                            'union_dues': payroll_taxes.get("union_dues"),
                        }
                        
                        # Create Payroll record
                        payroll_record = Payroll.objects.create(**payroll_defaults)
                        stored_records.append({
                            'id': payroll_record.id,
                            'ee_id': ee_id,
                            'client_id': client_id,
                            'batch_id': batch_id
                        })
                        
                        self.logger.info(f"Successfully stored payroll data for ee_id: {ee_id}, client_id: {client_id}")
                        
                    except Exception as e:
                        error_msg = f"Error storing payroll data for ee_id {payroll_item.get('ee_id')}: {str(e)}"
                        self.logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                        continue
            
            result = {
                "status": "success" if stored_records else "error",
                "stored_count": len(stored_records),
                "stored_records": stored_records
            }
            
            if errors:
                result["errors"] = errors
                result["status"] = "partial_success" if stored_records else "error"
            
            return result
            
        except Exception as e:
            error_msg = f"Error in store_payroll_data: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}


