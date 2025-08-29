from datetime import datetime, date
from django.db import transaction
import logging
import traceback as t
from processor.models import (StateTaxLevyAppliedRule,ExemptConfig,WithholdingLimit,WithholdingRules,CreditorDebtAppliedRule,StateTaxLevyConfig, StateTaxLevyExemptAmtConfig, CreditorDebtAppliedRule,AddExemptions,StdExemptions,ThresholdAmount,StateTaxLevyAppliedRule, StateTaxLevyExemptAmtConfig, StateTaxLevyConfig)
from user_app.models import ( EmployeeDetail, 
    EmployeeBatchData, GarnishmentBatchData, PayrollBatchData
)
from processor.serializers import (ThresholdAmountSerializer, AddExemptionSerializer, StdExemptionSerializer,
    StateTaxLevyConfigSerializers, StateTaxLevyExemptAmtConfigSerializers
)
from user_app.serializers import EmployeeDetailSerializer

from processor.garnishment_library.calculations import (StateAbbreviations,ChildSupport,FranchaiseTaxBoard,
                    GarFeesRulesEngine,MultipleGarnishmentPriorityOrder,StateTaxLevyCalculator,CreditorDebtCalculator,FederalTax,StudentLoanCalculator)
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    GarnishmentTypeResponse as GR,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    CalculationMessages as CM,
    CommonConstants,
)
from typing import Dict, Set, List, Any
logger = logging.getLogger(__name__)


INSUFFICIENT_PAY = "Garnishment cannot be deducted due to insufficient pay"

class CalculationDataView:
    """
    Service class to handle all garnishment calculations and database operations.
    """

    def preload_config_data(self, garnishment_types: Set[str]) -> Dict[str, Any]:
        """
        Preloads configuration data for the requested garnishment types.
        Enhanced with better error handling and logging.
        """
        config_data = {}
        loaded_types = []
        
        
        try:
            if GT.STATE_TAX_LEVY in garnishment_types:
                try:
                    queryset = StateTaxLevyExemptAmtConfig.objects.all()
                    serializer = StateTaxLevyExemptAmtConfigSerializers(queryset, many=True)
                    config_data[GT.STATE_TAX_LEVY] = serializer.data
                    loaded_types.append(GT.STATE_TAX_LEVY)
                except Exception as e:
                    logger.error(f"Error loading {GT.STATE_TAX_LEVY} config: {e}")

            if GT.CREDITOR_DEBT in garnishment_types:
                try:
                    queryset = ThresholdAmount.objects.select_related('config').all()
                    serializer = ThresholdAmountSerializer(queryset, many=True)
                    config_data[GT.CREDITOR_DEBT] = serializer.data
                    loaded_types.append(GT.CREDITOR_DEBT)
                except Exception as e:
                    logger.error(f"Error loading {GT.CREDITOR_DEBT} config: {e}")
                    
            if GT.FEDERAL_TAX_LEVY in garnishment_types:
                try:
                    # Get additional exemptions
                    add_exempt = AddExemptions.objects.select_related('year', 'fs').all()
                    add_serializer = AddExemptionSerializer(add_exempt, many=True)
                    config_data["federal_add_exempt"] = add_serializer.data
                    
                    # Get standard exemptions
                    std_exempt = StdExemptions.objects.select_related('year', 'fs', 'pp').all()
                    std_serializer = StdExemptionSerializer(std_exempt, many=True)

                    config_data["federal_std_exempt"] = std_serializer.data
                    
                    loaded_types.append(GT.FEDERAL_TAX_LEVY)
                except Exception as e:
                    logger.error(f"Error loading {GT.FEDERAL_TAX_LEVY} config: {e}")


            if GT.CHILD_SUPPORT in garnishment_types:
                pass
                # try:
                #     withholding_rules = WithholdingRules.objects.select_related('state').all()

                #     serializer = WithholdingRulesSerializer(withholding_rules, many=True)

                #     config_data[GT.CHILD_SUPPORT] = serializer.data
                    

                #     loaded_types.append(GT.CHILD_SUPPORT)
                # except Exception as e:
                #     logger.error(f"Error loading {GT.CHILD_SUPPORT} config: {e}")

            if "franchise_tax_board" in garnishment_types:
                try:
                    queryset = ExemptConfig.objects.select_related('state','pay_period','garnishment_type').filter(garnishment_type=6)

                    config_ids = queryset.values_list("id", flat=True)

                    # Get ThresholdAmount records linked to those configs
                    threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)

                    serializer = ThresholdAmountSerializer(threshold_qs, many=True)
                    config_data["franchise_tax_board"] = serializer.data

                    loaded_types.append("franchise_tax_board")

                    logger.info(f"Successfully loaded config for types: {loaded_types}")
                except Exception as e:
                    logger.error(f"Error loading {GT.FEDERAL_TAX_LEVY} config: {e}")
            
        except Exception as e:
            logger.error(f"Critical error preloading config data: {e}", exc_info=True)
            
        return config_data


    def validate_fields(self, record, required_fields):
        """
        Validates required fields and returns a list of missing fields.
        Uses set operations for efficiency if required_fields is large.
        """
        if len(required_fields) > 10:
            return list(set(required_fields) - set(record))
        return [field for field in required_fields if field not in record]

    def _get_employee_details(self, employee_id):
        """
        Fetches employee details by ID.
        Returns serialized data or None if not found.
        """
        try:
            obj = EmployeeDetail.objects.get(ee_id=employee_id)
            serializer = EmployeeDetailSerializer(obj)
            return serializer.data
        except EmployeeDetail.DoesNotExist:
            return None
        except Exception as e:
            logger.error(
                f"Error fetching employee details for {employee_id}: {e}")
            return None

    def is_garnishment_fee_deducted(self, record):
        """
        Determines if garnishment fees can be deducted for the employee.
        Returns True, False, or None (if employee not found).
        """
        employee_data = self._get_employee_details(
            record[EE.EMPLOYEE_ID])
        if employee_data is None:
            return None
        suspended_till_str = employee_data.get(
            'garnishment_fees_suspended_till')
        if not suspended_till_str:
            return True
        try:
            suspended_date = datetime.strptime(
                suspended_till_str, "%Y-%m-%d").date()
            return date.today() >= suspended_date
        except Exception as e:
            logger.warning(
                f"Malformed suspension date for employee {record[EE.EMPLOYEE_ID]}: {e}")
            return True

    def get_garnishment_fees(self, record, total_withhold_amt):
        """
        Calculates garnishment fees based on employee data and suspension status.
        """
        is_deductible = self.is_garnishment_fee_deducted(record)
        employee_id = record.get(EE.EMPLOYEE_ID)
        work_state = record.get(EE.WORK_STATE)
        try:
            if is_deductible is None:
                fees = GarFeesRulesEngine(work_state).apply_rule(
                    record, total_withhold_amt)
                return f"{fees}, {employee_id} is not registered. Please register the employee first to suspend garnishment fees calculation."
            elif is_deductible:
                return GarFeesRulesEngine(work_state).apply_rule(record, total_withhold_amt)
            else:
                employee_data = self._get_employee_details(employee_id)
                suspended_date = employee_data.get(
                    'garnishment_fees_suspended_till', 'N/A')
                return f"Garnishment fees cannot be deducted due to the suspension of garnishment fees until {suspended_date}"
        except Exception as e:
            logger.error(
                f"Error calculating garnishment fees for {employee_id}: {e}")
            return f"Error calculating garnishment fees: {e}"


    def get_rounded_garnishment_fee(self, work_state, record, withholding_amt):
        """
        Applies garnishment fee rule and rounds the result if it is numeric.
        """
        try:
            fee = GarFeesRulesEngine(work_state).apply_rule(
                record, withholding_amt)
            if isinstance(fee, (int, float)):
                return round(fee, 2)
            return fee
        except Exception as e:
            logger.error(f"Error rounding garnishment fee: {e}")
            return f"Error calculating garnishment fee: {e}"

    def calculate_garnishment(self, garnishment_type, record, config_data):
        """
        Handles garnishment calculations based on type.
        """
        garnishment_type_lower = garnishment_type.lower()
        garnishment_rules = {
            GT.CHILD_SUPPORT: {
                "fields": [
                    EE.ARREARS_GREATER_THAN_12_WEEKS, EE.SUPPORT_SECOND_FAMILY,
                    CA.GROSS_PAY, PT.PAYROLL_TAXES
                ],
                "calculate": self.calculate_child_support

            },
            GT.FEDERAL_TAX_LEVY: {
                "fields": [EE.FILING_STATUS, EE.PAY_PERIOD, CA.NET_PAY, EE.AGE, EE.IS_BLIND, EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE],
                "calculate": self.calculate_federal_tax
            },
            GT.STUDENT_DEFAULT_LOAN: {
                "fields": [CA.GROSS_PAY, EE.PAY_PERIOD, EE.NO_OF_STUDENT_DEFAULT_LOAN, PT.PAYROLL_TAXES],
                "calculate": self.calculate_student_loan
            },
            GT.STATE_TAX_LEVY: {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE
                ],
                "calculate": self.calculate_state_tax_levy
            },
            GT.CREDITOR_DEBT: {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_creditor_debt
            },
            "franchise_tax_board": {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_franchise_tax_board
            },

        }
        rule = garnishment_rules.get(garnishment_type_lower)
        if not rule:
            return {"error": f"Unsupported garnishment type: {garnishment_type}"}
        required_fields = rule["fields"]
        missing_fields = self.validate_fields(record, required_fields)
        if missing_fields:
            return {"error": f"Missing fields in record: {', '.join(missing_fields)}"}
        try:
            return rule["calculate"](record, config_data)
        except Exception as e:
            logger.error(f"Error in {garnishment_type} calculation: {e}")
            return {"error": f"Error calculating {garnishment_type}: {e}"}

    def _handle_insufficient_pay_garnishment(self, record, disposable_earning, total_mandatory_deduction_obj):
        """
        Helper to set insufficient pay messages and common fields.
        """
        record[CR.AGENCY] = [{CR.WITHHOLDING_AMT: [
            {CR.GARNISHMENT_AMOUNT: INSUFFICIENT_PAY}]}]
        record[CR.ER_DEDUCTION] = {
            CR.GARNISHMENT_FEES: "Garnishment fees cannot be deducted due to insufficient pay"}
        record[CR.WITHHOLDING_LIMIT_RULE] = CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
        record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
            total_mandatory_deduction_obj, 2)
        record[CR.DISPOSABLE_EARNING] = round(disposable_earning, 2)
        record[CR.WITHHOLDING_BASIS] = CM.NA
        record[CR.WITHHOLDING_CAP] = CM.NA
        return record

    def calculate_child_support(self, record, config_data=None):
        """
        Calculate child support garnishment.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            result = ChildSupport(work_state).calculate(record)
            child_support_data = result["result_amt"]
            arrear_amount_data = result["arrear_amt"]
            ade, de, mde = result["ade"], result["de"], result["mde"]
            total_withhold_amt = sum(
                child_support_data.values()) + sum(arrear_amount_data.values())
            if total_withhold_amt <= 0:
                record.update({
                    CR.AGENCY: [
                        {CR.WITHHOLDING_AMT: [{CR.GARNISHMENT_AMOUNT: INSUFFICIENT_PAY}
                                              for _ in child_support_data]},
                        {"arrear": [{CR.WITHHOLDING_ARREAR: INSUFFICIENT_PAY}
                                    for _ in arrear_amount_data]}
                    ],
                    CR.ER_DEDUCTION: {CR.GARNISHMENT_FEES: "Garnishment fees cannot be deducted due to insufficient pay"},
                    CR.WITHHOLDING_BASIS: CM.NA,
                    CR.WITHHOLDING_CAP: CM.NA
                })
            else:
                record.update({
                    CR.AGENCY: [
                        {CR.WITHHOLDING_AMT: [{CR.GARNISHMENT_AMOUNT: amt}
                                              for amt in child_support_data.values()]},
                        {CR.ARREAR: [{CR.WITHHOLDING_ARREAR: amt}
                                     for amt in arrear_amount_data.values()]}
                    ],
                    CR.ER_DEDUCTION: {CR.GARNISHMENT_FEES: self.get_garnishment_fees(record, total_withhold_amt)},
                    CR.DISPOSABLE_EARNING: round(de, 2),
                    CR.ALLOWABLE_DISPOSABLE_EARNING: round(ade, 2),
                    CR.TOTAL_MANDATORY_DEDUCTION: round(mde, 2),
                    CR.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                    CR.WITHHOLDING_BASIS: CM.NA,
                    CR.WITHHOLDING_CAP: CM.NA
                })
            return record
        except Exception as e:
            logger.error(f"Error calculating child support: {e}")
            return {"error": f"Error calculating child support: {e}"}

    def calculate_federal_tax(self, record, config_data):
        """
        Calculate federal tax garnishment.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            add_exempt={"federal_add_exempt":config_data["federal_add_exempt"]}
            std_exempt={"federal_std_exempt":config_data["federal_std_exempt"]}
            result = FederalTax().calculate(record,std_exempt,add_exempt)

            if result == 0:
                record[CR.AGENCY] = [
                    {CR.WITHHOLDING_AMT: [{GR.FEDERAL_TAX_LEVY: INSUFFICIENT_PAY}]}]
            else:
                record[CR.AGENCY] = [
                    {CR.WITHHOLDING_AMT: [{GR.FEDERAL_TAX_LEVY: result}]}]
            record[CR.ER_DEDUCTION] = {
                CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(work_state, record, result)}
            record[CR.WITHHOLDING_BASIS] = CM.NA
            record[CR.WITHHOLDING_CAP] = CM.NA
            return record
        except Exception as e:
            logger.error(f"Error calculating federal tax: {e}")
            return {"error": f"Error calculating federal tax: {e}"}

    def calculate_student_loan(self, record, config_data=None):
        """
        Calculate student loan garnishment.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            result = StudentLoanCalculator().calculate(record)
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(record)
            loan_amt = result["student_loan_amt"]

            if len(loan_amt) == 1:
                record[CR.AGENCY] = [{
                    CR.WITHHOLDING_AMT: [
                        {GR.STUDENT_DEFAULT_LOAN: loan_amt.values()}]}]
            else:
                record[CR.AGENCY] = [{
                    CR.WITHHOLDING_AMT: [{GR.STUDENT_DEFAULT_LOAN: amt}
                                     for amt in loan_amt.values()]}]
            total_student_loan_amt = 0 if any(isinstance(
                val, str) for val in loan_amt.values()) else sum(loan_amt.values())
            record[CR.ER_DEDUCTION] = {CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                work_state, record, total_student_loan_amt)}
            record[CR.WITHHOLDING_BASIS] = CM.NA
            record[CR.WITHHOLDING_CAP] = CM.NA
            record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
                    total_mandatory_deduction_val, 2)
            record[CR.DISPOSABLE_EARNING] = result[CR.DISPOSABLE_EARNING]
            return record
        except Exception as e:
            logger.error(f"Error calculating student loan: {e}")
            return {"error": f"Error calculating student loan: {e}"}

    def calculate_state_tax_levy(self, record, config_data=None):
        """
        Calculate state tax levy garnishment.
        """
        try:
            state_tax_view = StateTaxLevyCalculator()
            work_state = record.get(EE.WORK_STATE)
            result = state_tax_view.calculate(
                record, config_data[GT.STATE_TAX_LEVY])
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(record)
            if result == CommonConstants.NOT_FOUND:
                return None
            if isinstance(result, dict) and result.get(CR.WITHHOLDING_AMT, 0) <= 0:
                return self._handle_insufficient_pay_garnishment(
                    record,
                    result.get(CR.DISPOSABLE_EARNING, 0),
                    total_mandatory_deduction_val
                )
            else:
                record[CR.AGENCY] = [{
                    CR.WITHHOLDING_AMT: [
                        {CR.GARNISHMENT_AMOUNT: round(
                            result[CR.WITHHOLDING_AMT], 2)}
                    ]
                }]
                record[CR.ER_DEDUCTION] = {
                    CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                        work_state, record, result[CR.WITHHOLDING_AMT]
                    )
                }
                
                record[CR.WITHHOLDING_LIMIT_RULE] = CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
                record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
                    total_mandatory_deduction_val, 2)
                record[CR.DISPOSABLE_EARNING] = round(
                    result[CR.DISPOSABLE_EARNING], 2)
                record[CR.WITHHOLDING_BASIS] = result.get(CR.WITHHOLDING_BASIS)
                record[CR.WITHHOLDING_CAP] = result.get(CR.WITHHOLDING_CAP)
                return record
        except Exception as e:
            logger.error(f"Error calculating state tax levy: {e}")
            return {"error": f"Error calculating state tax levy: {e}"}

    def calculate_creditor_debt(self, record, config_data=None):
        """
        Calculate creditor debt garnishment.
        """
        try:
            creditor_debt_calculator = CreditorDebtCalculator()
            work_state = record.get(EE.WORK_STATE)
            result = creditor_debt_calculator.calculate(
                record, config_data[GT.CREDITOR_DEBT])
            if isinstance(result, tuple):
                result = result[0]
            if result == CommonConstants.NOT_FOUND:
                return None
            elif result == CommonConstants.NOT_PERMITTED:
                return CommonConstants.NOT_PERMITTED
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(record)
            if result[CR.WITHHOLDING_AMT] <= 0:
                return self._handle_insufficient_pay_garnishment(
                    record, result[CR.DISPOSABLE_EARNING], total_mandatory_deduction_val)
            else:
                record[CR.AGENCY] = [{CR.WITHHOLDING_AMT: [
                    {CR.CREDITOR_DEBT: max(round(result[CR.WITHHOLDING_AMT], 2), 0)}]}]
                record[CR.DISPOSABLE_EARNING] = round(
                    result[CR.DISPOSABLE_EARNING], 2)
                record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
                    total_mandatory_deduction_val, 2)
                record[CR.ER_DEDUCTION] = {CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                    work_state, record, result[CR.WITHHOLDING_AMT])}
                record[CR.WITHHOLDING_LIMIT_RULE] = CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
                record[CR.WITHHOLDING_BASIS] = result.get(CR.WITHHOLDING_BASIS)
                record[CR.WITHHOLDING_CAP] = result.get(CR.WITHHOLDING_CAP)
                return record
        except Exception as e:
            logger.error(f"Error calculating creditor debt: {e}")
            return {"error": f"Error calculating creditor debt: {e}"}
        
    def calculate_franchise_tax_board(self, record, config_data=None):
        """
        Calculate creditor debt garnishment.
        """
        try:
            creditor_debt_calculator = FranchaiseTaxBoard()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            result = creditor_debt_calculator.calculate(
                record, config_data["franchise_tax_board"])
            if isinstance(result, tuple):
                result = result[0]
            if result == CommonConstants.NOT_FOUND:
                return None
            elif result == CommonConstants.NOT_PERMITTED:
                return CommonConstants.NOT_PERMITTED
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(payroll_taxes)
            if result[CR.WITHHOLDING_AMT] <= 0:
                return self._handle_insufficient_pay_garnishment(
                    record, result[CR.DISPOSABLE_EARNING], total_mandatory_deduction_val)
            else:
                record[CR.AGENCY] = [{CR.WITHHOLDING_AMT: [
                    {GT.FRANCHISE_TAX_BOARD: max(round(result[CR.WITHHOLDING_AMT], 2), 0)}]}]
                record[CR.DISPOSABLE_EARNING] = round(
                    result[CR.DISPOSABLE_EARNING], 2)
                record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
                    total_mandatory_deduction_val, 2)
                record[CR.ER_DEDUCTION] = {
                    CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                    work_state, record, result[CR.WITHHOLDING_AMT]
                    )}
                record[CR.WITHHOLDING_LIMIT_RULE] = CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
                record[CR.WITHHOLDING_BASIS] = result.get(CR.WITHHOLDING_BASIS)
                record[CR.WITHHOLDING_CAP] = result.get(CR.WITHHOLDING_CAP)
                return record
        except Exception as e:
            logger.error(f"Error calculating franchise tax board: {e}")
            return {"error": f"Error calculating franchise tax board: {e}"}
        

    def calculate_multiple_garnishment(self, record, config_data=None):
        """
        Calculate multiple garnishment and merge results with input record.
        """
        try:
            # Create copy of original record to preserve input data
            enhanced_record = record.copy()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            
            multiple_garnishment = MultipleGarnishmentPriorityOrder(record, config_data)
            work_state = record.get(EE.WORK_STATE)
            result = multiple_garnishment.calculate()
            
            if result == CommonConstants.NOT_FOUND:
                enhanced_record['calculation_status'] = 'not_found'
                enhanced_record['error'] = 'No garnishment configuration found'
                return enhanced_record
                
            elif result == CommonConstants.NOT_PERMITTED:
                enhanced_record['calculation_status'] = 'not_permitted'
                enhanced_record['message'] = 'Garnishment not permitted for this case'
                return enhanced_record
            
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Transform garnishment_data to include calculation results
            enhanced_garnishment_data = []
            total_withheld = 0.0
            
            # Process each garnishment type from the calculation results
            for garnishment_type, type_result in result.items():
                if isinstance(type_result, dict):
                    # Find matching garnishment data from input
                    original_garnishment = None
                    for garnishment in record.get(EE.GARNISHMENT_DATA, []):
                        if garnishment.get('type', '').lower().replace(' ', '_') == garnishment_type.lower().replace(' ', '_'):
                            original_garnishment = garnishment
                            break
                    
                    if original_garnishment:
                        enhanced_type_data = {
                            'type': garnishment_type,
                            'cases': []
                        }
                        
                        original_cases = original_garnishment.get('data', [])
                        
                        # Handle child support specific structure
                        if garnishment_type == 'child_support':
                            result_amounts = type_result.get('result_amt', {})
                            arrear_amounts = type_result.get('arrear_amt', {})
                            
                            type_total_withheld = 0.0
                            
                            for i, original_case in enumerate(original_cases):
                                enhanced_case = original_case.copy()
                                case_key_result = f"child support amount{i+1}"
                                case_key_arrear = f"arrear amount{i+1}"
                                
                                # Get individual amounts from calculation result
                                garnishment_amount = result_amounts.get(case_key_result, 0)
                                arrear_amount = arrear_amounts.get(case_key_arrear, 0)
                                
                                # For child support, the full amounts are typically withheld if available
                                current_support_withheld = garnishment_amount
                                arrear_withheld = arrear_amount
                                
                                # Total withheld for this case
                                case_total_withheld = current_support_withheld + arrear_withheld
                                
                                # Calculate remaining balance (should be 0 if fully withheld)
                                total_required = garnishment_amount + arrear_amount
                                remaining_balance = max(0, total_required - case_total_withheld)
                                
                                enhanced_case.update({
                                    'withholding_amount': round(garnishment_amount, 2),
                                    'arrear_amount': round(arrear_amount, 2),
                                    'arrear_withheld': round(arrear_withheld, 2),
                                    'remaining_balance': round(remaining_balance, 2),
                                    'calculation_status': type_result["calculation_status"]
                                })
                                enhanced_type_data['cases'].append(enhanced_case)
                                type_total_withheld += case_total_withheld
                            
                            total_withheld += type_total_withheld
                        
                        # Handle other garnishment types (student loan, creditor debt, etc.)
                        else:
                            withholding_amount = type_result.get('withholding_amt', 0)
                            status = type_result.get('status', 'processed')
                            
                            # Calculate per case amounts
                            total_cases = len(original_cases)
                            per_case_withholding = withholding_amount / total_cases if total_cases > 0 else 0
                            
                            type_total_withheld = 0.0
                            
                            for original_case in original_cases:
                                enhanced_case = original_case.copy()
                                
                                # Get ordered amount (required amount)
                                ordered_amount = enhanced_case.get('ordered_amount', 0)
                                
                                # Calculate actual withholding for this case
                                case_withholding = per_case_withholding if status != 'skipped_due_to_limit' else 0
                                
                                # Calculate remaining balance
                                remaining_balance = max(0, ordered_amount - case_withholding)

                                enhanced_case.update({
                                    'withholding_amount': round(case_withholding, 2),
                                    'remaining_balance': round(remaining_balance, 2),
                                    'calculation_status': type_result["calculation_status"],
                                    CR.WITHHOLDING_LIMIT_RULE : CommonConstants.WITHHOLDING_RULE_PLACEHOLDER,
                                    CR.WITHHOLDING_BASIS : type_result.get(CR.WITHHOLDING_BASIS, CM.NA),
                                    CR.WITHHOLDING_CAP : type_result.get(CR.WITHHOLDING_CAP, CM.NA)
                                    
                                })
                                enhanced_type_data['cases'].append(enhanced_case)
                                type_total_withheld += case_withholding
                            
                            total_withheld += type_total_withheld
                        
                        # Add type summary
                        enhanced_type_data['type_summary'] = {
                            'total_cases': len(enhanced_type_data['cases']),
                            'status': type_result.get('status', 'processed'),
                            'total_withheld': round(type_total_withheld if garnishment_type == 'child_support' or garnishment_type in ['student default loan', 'creditor debt'] else type_result.get('garnishment_amount', type_result.get('withholding_amt', 0)), 2)
                        }
                        
                        enhanced_garnishment_data.append(enhanced_type_data)
            
            # Update the record with enhanced garnishment data
            enhanced_record[EE.GARNISHMENT_DATA] = enhanced_garnishment_data
            
            # Add calculation summary
            enhanced_record['calculation_summary'] = {
                'twenty_five_percent_of_de':round(result[GT.CHILD_SUPPORT]["twenty_five_percent_of_de"], 2),
                'disposable_earnings': round(result[GT.CHILD_SUPPORT]["de"], 2),
                'allowable_disposable_earnings': round(result[GT.CHILD_SUPPORT]['ade'], 2),
                'total_mandatory_deduction': round(total_mandatory_deduction_val, 2),
            }
            
            # Add employer deduction information
            enhanced_record[CR.ER_DEDUCTION] = {
                CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                    work_state, enhanced_record, total_withheld
                )
            }
    
            return enhanced_record
            
        except Exception as e:
            import traceback as t
            logger.error(f"Error calculating multiple garnishment: {e}")
            enhanced_record = record.copy()
            enhanced_record['calculation_status'] = 'error'
            enhanced_record['error'] = f"Error calculating multiple garnishment: {e}"
            return enhanced_record
                
    def calculate_garnishment_wrapper(self, record, config_data):
            """
            Wrapper function for parallel processing of garnishment calculations.
            """
            try:
                garnishment_data = record.get("garnishment_data")
                if not garnishment_data:
                    return None
                garnishment_type = garnishment_data[0].get(
                    EE.GARNISHMENT_TYPE, "").strip().lower()
                result = self.calculate_garnishment(
                    garnishment_type, record, config_data)
                if result is None:
                    return CommonConstants.NOT_FOUND
                elif result == CommonConstants.NOT_PERMITTED:
                    return CommonConstants.NOT_PERMITTED
                else:
                    return result
            except Exception as e:
                logger.error(f"Error in garnishment wrapper: {e}")
                return {"error": f"Error in garnishment wrapper: {e}"}

    def calculate_garnishment_result(self, case_info,batch_id, config_data):
        """
        Calculates garnishment result for a single case.
        """
        try:
            state = StateAbbreviations(case_info.get(
                EE.WORK_STATE)).get_state_name_and_abbr()
            ee_id = case_info.get(EE.EMPLOYEE_ID)
            is_multiple_garnishment_type=case_info.get("is_multiple_garnishment_type")
            if is_multiple_garnishment_type ==True:
                calculated_result=self.calculate_multiple_garnishment(case_info, config_data=config_data)
            else:
                calculated_result = self.calculate_garnishment_wrapper(
                case_info, config_data)
            if isinstance(calculated_result, dict) and 'error' in calculated_result:
                return {
                    "error": calculated_result["error"],
                    "status_code": calculated_result.get("status_code", 500),
                    "employee_id": ee_id,
                    "state": state
                }
            if calculated_result == CommonConstants.NOT_FOUND:
                return {
                    "error": f"Garnishment could not be calculated for employee {ee_id} because the state of {state} has not been implemented yet."
                }
            elif calculated_result == CommonConstants.NOT_PERMITTED:
                return {"error": f"In {state}, garnishment for creditor debt is not permitted."}
            elif not calculated_result:
                return {
                    "error": f"Could not calculate garnishment for employee: {ee_id}"
                }
            return calculated_result
        except Exception as e:
            logger.error(
                f"Unexpected error during garnishment calculation for employee {case_info.get(EE.EMPLOYEE_ID)}: {e}")
            return {
                "error": f"Unexpected error during garnishment calculation for employee {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"
            }

    def process_and_store_case(self, case_info, batch_id, config_data):
        try:
            with transaction.atomic():
                ee_id = case_info.get(EE.EMPLOYEE_ID)
                state = StateAbbreviations(case_info.get(
                    EE.WORK_STATE)).get_state_name_and_abbr().title()
                pay_period = case_info.get(EE.PAY_PERIOD).title()

                result = self.calculate_garnishment_result(
                    case_info, batch_id, config_data)

                withholding_basis = result.get(CR.WITHHOLDING_BASIS)
                withholding_cap = result.get(CR.WITHHOLDING_CAP)

                if isinstance(result, dict) and result.get("error"):
                    return result

                garnishment_type_data = result.get("garnishment_data")
                
                # Process rules for all garnishment types (not just the first one)
                if garnishment_type_data:
                    for garnishment_group in garnishment_type_data:
                        garnishment_type = garnishment_group.get("type", "").lower()
                        garnishment_data_list = garnishment_group.get("data", [])
                        
                        # Process each case within the garnishment type
                        for garnishment_item in garnishment_data_list:
                            case_id = garnishment_item.get(EE.CASE_ID, 0)
                            
                            if garnishment_type == GT.STATE_TAX_LEVY.lower():
                                try:
                                    rule = StateTaxLevyConfig.objects.get(
                                        state__iexact=state)

                                    serializer_data = StateTaxLevyConfigSerializers(
                                        rule).data
                                    serializer_data.update({
                                        CR.WITHHOLDING_BASIS: withholding_basis,
                                        CR.WITHHOLDING_CAP: withholding_cap,
                                        EE.EMPLOYEE_ID: ee_id,
                                        EE.PAY_PERIOD: pay_period
                                    })
                                    serializer_data.pop('id', None)
                                    StateTaxLevyAppliedRule.objects.update_or_create(
                                        case_id=case_id, defaults=serializer_data)
                                except StateTaxLevyConfig.DoesNotExist:
                                    pass

                            elif garnishment_type == GT.CREDITOR_DEBT.lower():
                                data = {
                                    EE.EMPLOYEE_ID: ee_id,
                                    CR.WITHHOLDING_BASIS: withholding_basis,
                                    EE.STATE: state,
                                    CR.WITHHOLDING_CAP: withholding_cap,
                                    EE.PAY_PERIOD: pay_period
                                }
                                CreditorDebtAppliedRule.objects.update_or_create(
                                    case_id=case_id, defaults=data)

                first_case_id = 0
                if case_info.get("garnishment_data"):
                    first_group = case_info.get("garnishment_data", [{}])[0]
                    first_case_data = first_group.get("data", [{}])
                    if first_case_data:
                        first_case_id = first_case_data[0].get(EE.CASE_ID, 0)

                employee_defaults = {
                    EE.CASE_ID: first_case_id,
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

                # Store or update Payroll Taxes for each case
                payroll_data = case_info.get(PT.PAYROLL_TAXES, {})
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

                # Store payroll tax data (one record per employee, using first case_id)
                PayrollBatchData.objects.update_or_create(
                    case_id=first_case_id, defaults={**payroll_defaults, "ee_id": ee_id})

                # Deduplicate and prepare Garnishment Data
                unique_garnishments_to_create = {}
                for garnishment_group in case_info.get(CA.GARNISHMENT_DATA, []):
                    garnishment_type = garnishment_group.get(
                        EE.GARNISHMENT_TYPE, garnishment_group.get("type", ""))  
                    for garnishment in garnishment_group.get("data", []):
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

                result.pop(CR.WITHHOLDING_BASIS, None)  # Use None as default to avoid KeyError
                result.pop(CR.WITHHOLDING_CAP, None)
                return result
                
        except Exception as e:
            return {"error": f"Error processing case for employee {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"}

    def get_all_garnishment_types(self, cases_data: List[Dict]) -> Set[str]:
        """
        Extract all unique garnishment types from the cases data.
        Handles both single and multi-garnishment cases.
        """
        garnishment_types = set()
        
        for case in cases_data:
            garnishment_data = case.get(EE.GARNISHMENT_DATA, [])
            
            for garnishment in garnishment_data:
                garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get('type')
                if garnishment_type:
                    normalized_type = garnishment_type.lower().strip()
                    garnishment_types.add(normalized_type)
                    
        return garnishment_types

    def is_multi_garnishment_case(self, case_data: Dict) -> bool:
        """
        Determine if a case contains multiple garnishment types.
        Returns True if more than one garnishment type is present.
        """
        garnishment_data = case_data.get(EE.GARNISHMENT_DATA, [])
        return len(garnishment_data) > 1

    def get_case_garnishment_types(self, case_data: Dict) -> Set[str]:
        """
        Extract garnishment types for a specific case.
        Used for multi-garnishment case processing.
        """
        garnishment_types = set()
        garnishment_data = case_data.get(EE.GARNISHMENT_DATA, [])
        
        for garnishment in garnishment_data:
            garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get('type')
            if garnishment_type:
                normalized_type = garnishment_type.lower().strip()
                garnishment_types.add(normalized_type)
                
        return garnishment_types

    def filter_config_for_case(self, full_config_data: Dict, case_garnishment_types: Set[str]) -> Dict:
        """
        Filter configuration data to include only relevant types for a specific case.
        This is particularly useful for multi-garnishment cases.
        """
        filtered_config = {}
        
        for garnishment_type in case_garnishment_types:
            if garnishment_type in full_config_data:
                filtered_config[garnishment_type] = full_config_data[garnishment_type]
                    
        return filtered_config        