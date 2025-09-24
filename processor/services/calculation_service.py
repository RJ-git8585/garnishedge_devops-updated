from datetime import datetime, date
from django.db import transaction
import logging
import traceback as t
from processor.models import (StateTaxLevyAppliedRule,GarnishmentFees,ExemptConfig,WithholdingLimit,WithholdingRules,CreditorDebtAppliedRule,StateTaxLevyConfig, StateTaxLevyExemptAmtConfig, CreditorDebtAppliedRule,AddExemptions,StdExemptions,ThresholdAmount,StateTaxLevyAppliedRule, StateTaxLevyExemptAmtConfig, StateTaxLevyConfig)
from user_app.models import ( EmployeeDetail, 
    EmployeeBatchData, GarnishmentBatchData, PayrollBatchData
)
from processor.serializers import (ThresholdAmountSerializer, AddExemptionSerializer, StdExemptionSerializer,GarnishmentFeesSerializer,
    StateTaxLevyConfigSerializers, StateTaxLevyExemptAmtConfigSerializers
)
from user_app.serializers import EmployeeDetailSerializer

from processor.garnishment_library.calculations import (StateAbbreviations,ChildSupport,FranchaiseTaxBoard,ftb_ewot,WithholdingProcessor,Bankruptcy,
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
    GarnishmentResultFields as GRF,
    ConfigDataKeys as CDK,
    ErrorMessages as EM,
    CalculationResultKeys as CRK,
    GarnishmentDataKeys as GDK,
)
from typing import Dict, Set, List, Any
logger = logging.getLogger(__name__)


INSUFFICIENT_PAY = EM.INSUFFICIENT_PAY

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
                    queryset = StateTaxLevyExemptAmtConfig.objects.select_related('state').all()
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

            if GT.FRANCHISE_TAX_BOARD in garnishment_types:
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
            
            if "bankruptcy" in garnishment_types:
                try:
                    queryset = ExemptConfig.objects.select_related('state','pay_period','garnishment_type').filter(garnishment_type=7)

                    config_ids = queryset.values_list("id", flat=True)

                    # Get ThresholdAmount records linked to those configs
                    threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)

                    serializer = ThresholdAmountSerializer(threshold_qs, many=True)
                    config_data["bankruptcy"] = serializer.data
                    loaded_types.append("bankruptcy")
                    logger.info(f"Successfully loaded config for types: {loaded_types}")
                except Exception as e:
                    logger.error(f"Error loading {GT.FEDERAL_TAX_LEVY} config: {e}")

            for type_name, type_id in GT.FTB_RELATED_TYPES.items():
                if type_name in garnishment_types:
                    try:
                        queryset = ExemptConfig.objects.select_related('state', 'pay_period', 'garnishment_type').filter(garnishment_type=type_id)
                        config_ids = queryset.values_list("id", flat=True)
                        threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)
                        serializer = ThresholdAmountSerializer(threshold_qs, many=True)
                        config_data[type_name] = serializer.data
                        loaded_types.append(type_name)
                        logger.info(f"Successfully loaded config for types: {loaded_types}")
                    except Exception as e:
                        logger.error(f"Error loading config for {type_name}: {e}")
            
        except Exception as e:
            logger.error(f"Critical error preloading config data: {e}", exc_info=True) 


        return config_data
    
    def preload_garnishment_fees(self) -> list:
        """
        Preloads garnishment fee configurations from the DB once.
        """
        try:
            fees = (
            GarnishmentFees.objects
            .select_related("state", "garnishment_type", "pay_period", "rule")
            .all()
            .order_by("-created_at")
        )
            serializer = GarnishmentFeesSerializer(fees, many=True)
            logger.info("Successfully loaded garnishment fee config")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading garnishment fees: {e}", exc_info=True)
            return []


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

    def get_garnishment_fees(self, record, total_withhold_amt,garn_fees=None):
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


    def get_rounded_garnishment_fee(self, work_state, record, withholding_amt,garn_fees=None):
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

    def calculate_garnishment(self, garnishment_type, record, config_data,garn_fees=None):
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
                "fields": [EE.FILING_STATUS, EE.PAY_PERIOD, CA.NET_PAY, EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE],
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
            GT.FRANCHISE_TAX_BOARD: {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_franchise_tax_board
            },
            GT.SPOUSAL_AND_MEDICAL_SUPPORT: {
                "fields": [
                    EE.ARREARS_GREATER_THAN_12_WEEKS, EE.SUPPORT_SECOND_FAMILY,
                    CA.GROSS_PAY, PT.PAYROLL_TAXES
                ],
                "calculate": self.calculate_child_support_priority
            },
            GT.BANKRUPTCY: {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, GT.SPOUSAL_SUPPORT_AMOUNT, GT.BANKRUPTCY_AMOUNT
                ],
                "calculate": self.calculate_bankruptcy
            },
            "ftb_ewot": {
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_ewot
            },
            "court_ordered_debt": {  
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_ewot
            },
            "ftb_vehicle": {  
                "fields": [
                    EE.GROSS_PAY, EE.WORK_STATE, EE.PAY_PERIOD, EE.FILING_STATUS
                ],
                "calculate": self.calculate_ewot
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
            return rule["calculate"](record, config_data,garn_fees)
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

    def _create_standardized_result(self, garnishment_type, record, calculation_result=None, error_message=None):
        """
        Creates a standardized result structure for garnishment calculations.
        This ensures consistency across all garnishment types.
        """
        result = {
            GRF.GARNISHMENT_TYPE: garnishment_type,
            GRF.EMPLOYEE_ID: record.get(EE.EMPLOYEE_ID),
            GRF.WORK_STATE: record.get(EE.WORK_STATE),
            GRF.CALCULATION_STATUS: GRF.SUCCESS if not error_message else GRF.ERROR,
            GRF.CALCULATION_TIMESTAMP: datetime.now().isoformat(),
            GRF.GARNISHMENT_DETAILS: {
                GRF.WITHHOLDING_AMOUNTS: [],
                GRF.ARREAR_AMOUNTS: [],
                GRF.TOTAL_WITHHELD: 0.0,
                GRF.GARNISHMENT_FEES: 0.0,
                GRF.NET_WITHHOLDING: 0.0
            },
            GRF.CALCULATION_METRICS: {
                GRF.DISPOSABLE_EARNINGS: 0.0,
                GRF.ALLOWABLE_DISPOSABLE_EARNINGS: 0.0,
                GRF.TOTAL_MANDATORY_DEDUCTIONS: 0.0,
                GRF.WITHHOLDING_BASIS: CM.NA,
                GRF.WITHHOLDING_CAP: CM.NA,
                GRF.WITHHOLDING_LIMIT_RULE: CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
            },
            CR.ER_DEDUCTION: {
                GRF.GARNISHMENT_FEES: 0.0,
                "total_employer_cost": 0.0
            }
        }
        
        if error_message:
            result[GRF.ERROR] = error_message
            result[GRF.CALCULATION_STATUS] = GRF.ERROR
            
        return result

    def calculate_child_support(self, record, config_data=None, garn_fees=None):
        """
        Calculate child support garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            calculation_result = ChildSupport(work_state).calculate(record)
            
            child_support_data = calculation_result[CRK.RESULT_AMT]
            arrear_amount_data = calculation_result[CRK.ARREAR_AMT]
            ade, de, mde = calculation_result[CRK.ADE], calculation_result[CRK.DE], calculation_result[CRK.MDE]
            
            total_withhold_amt = sum(child_support_data.values()) + sum(arrear_amount_data.values())
            
            # Create standardized result
            result = self._create_standardized_result(GT.CHILD_SUPPORT, record)
            
            if total_withhold_amt <= 0:
                # Handle insufficient pay scenario with case IDs
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                
                # Get case IDs for insufficient pay scenario
                garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                child_support_garnishment = None
                
                for garnishment in garnishment_data:
                    if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                        child_support_garnishment = garnishment
                        break
                
                if child_support_garnishment:
                    cases = child_support_garnishment.get(GDK.DATA, [])
                    withholding_amounts = []
                    arrear_amounts = []
                    
                    for case in cases:
                        case_id = case.get(EE.CASE_ID, GRF.UNKNOWN_CASE)
                        withholding_amounts.append({
                            GRF.AMOUNT: INSUFFICIENT_PAY, 
                            GRF.TYPE: GRF.CURRENT_SUPPORT,
                            GRF.CASE_ID: case_id
                        })
                        arrear_amounts.append({
                            GRF.AMOUNT: INSUFFICIENT_PAY, 
                            GRF.TYPE: GRF.ARREAR,
                            GRF.CASE_ID: case_id
                        })
                    
                    result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
                    result[GRF.GARNISHMENT_DETAILS][GRF.ARREAR_AMOUNTS] = arrear_amounts
                else:
                    # Fallback
                    result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                        {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.CURRENT_SUPPORT} 
                        for _ in child_support_data
                    ]
                    result[GRF.GARNISHMENT_DETAILS][GRF.ARREAR_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.ARREAR} 
                    for _ in arrear_amount_data
                    ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
            else:
                # Calculate garnishment fees
                garnishment_fees = self.get_garnishment_fees(record, total_withhold_amt, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                # Populate withholding amounts with actual case IDs
                withholding_amounts = []
                arrear_amounts = []
                
                # Get garnishment data from input to extract case IDs
                garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                child_support_garnishment = None
                
                # Find child support garnishment data
                for garnishment in garnishment_data:
                    if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                        child_support_garnishment = garnishment
                        break
                
                # Map amounts to case IDs
                if child_support_garnishment:
                    cases = child_support_garnishment.get(GDK.DATA, [])
                    child_support_amounts = list(child_support_data.values())
                    arrear_amounts_list = list(arrear_amount_data.values())
                    
                    for idx, case in enumerate(cases):
                        case_id = case.get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{idx}")
                        
                        # Add current support amount
                        if idx < len(child_support_amounts):
                            withholding_amounts.append({
                                GRF.AMOUNT: round(child_support_amounts[idx], 2),
                                GRF.TYPE: GRF.CURRENT_SUPPORT,
                                GRF.CASE_ID: case_id
                            })
                        
                        # Add arrear amount
                        if idx < len(arrear_amounts_list):
                            arrear_amounts.append({
                                GRF.AMOUNT: round(arrear_amounts_list[idx], 2),
                                GRF.TYPE: GRF.ARREAR,
                                GRF.CASE_ID: case_id
                            })
                else:
                    # Fallback to case_index if no garnishment data found
                    withholding_amounts = [
                        {GRF.AMOUNT: round(amt, 2), GRF.TYPE: GRF.CURRENT_SUPPORT, GRF.CASE_INDEX: idx}
                        for idx, amt in enumerate(child_support_data.values())
                    ]
                    arrear_amounts = [
                        {GRF.AMOUNT: round(amt, 2), GRF.TYPE: GRF.ARREAR, GRF.CASE_INDEX: idx}
                        for idx, amt in enumerate(arrear_amount_data.values())
                    ]
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
                result[GRF.GARNISHMENT_DETAILS][GRF.ARREAR_AMOUNTS] = arrear_amounts
                
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_withhold_amt, 2)
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(total_withhold_amt + garnishment_fees_amount, 2)
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(de, 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(ade, 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(mde, 2)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(total_withhold_amt + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} child support: {e}")
            return self._create_standardized_result(GT.CHILD_SUPPORT, record, error_message=f"{EM.ERROR_CALCULATING} child support: {e}")

    def calculate_federal_tax(self, record, config_data, garn_fees=None):
        """
        Calculate federal tax garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            #add_exempt = {CDK.FEDERAL_ADD_EXEMPT: config_data[CDK.FEDERAL_ADD_EXEMPT]}
            std_exempt = {CDK.FEDERAL_STD_EXEMPT: config_data[CDK.FEDERAL_STD_EXEMPT]}
            calculation_result = FederalTax().calculate(record, std_exempt)

            # Create standardized result
            result = self._create_standardized_result(GT.FEDERAL_TAX_LEVY, record)
            
            if calculation_result == 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.FEDERAL_TAX_LEVY}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
            else:
                # Calculate garnishment fees
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, calculation_result, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                withholding_amount = round(calculation_result, 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.FEDERAL_TAX_LEVY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(float(withholding_amount)+ float(garnishment_fees_amount), 2)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(float(withholding_amount)+ float(garnishment_fees_amount), 2)
                
                # Federal tax specific metrics
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = CM.NA
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = CM.NA
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} federal tax: {e}")
            return self._create_standardized_result(GT.FEDERAL_TAX_LEVY, record, error_message=f"{EM.ERROR_CALCULATING} federal tax: {e}")

    def calculate_student_loan(self, record, config_data=None, garn_fees=None):
        """
        Calculate student loan garnishment with standardized result structure.
        """
        try:
            work_state = record.get(EE.WORK_STATE)
            result = StudentLoanCalculator().calculate(record)
            total_mandatory_deduction_val = ChildSupport(
                work_state).calculate_md(record)
            loan_amt = result[CRK.STUDENT_LOAN_AMT]


            if len(loan_amt) == 1:
                if isinstance(loan_amt, (int, float,list,dict)):
                    record[CR.AGENCY] = [{
                        CR.WITHHOLDING_AMT: [
                            {GR.STUDENT_DEFAULT_LOAN: loan_amt.values()}]}]
                else:
                    record[CR.AGENCY] = [{
                        CR.WITHHOLDING_AMT: [
                            {GR.STUDENT_DEFAULT_LOAN: loan_amt}]}]
            else:
                record[CR.AGENCY] = [{
                    CR.WITHHOLDING_AMT: [{GR.STUDENT_DEFAULT_LOAN: amt}
                                     for amt in loan_amt.values()]}]
            total_student_loan_amt = 0 if any(isinstance(
                val, str) for val in loan_amt.values()) else sum(loan_amt.values())
            record[CR.ER_DEDUCTION] = {CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                work_state, record, total_student_loan_amt,garn_fees)}
            record[CR.WITHHOLDING_BASIS] = CM.NA
            record[CR.WITHHOLDING_CAP] = CM.NA
            # Create standardized result
            standardized_result = self._create_standardized_result(GT.STUDENT_DEFAULT_LOAN, record)
            
            # Calculate total student loan amount
            total_student_loan_amt = 0
            withholding_amounts = []
            
            # Get garnishment data from input to extract case IDs
            garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
            student_loan_garnishment = None
            
            # Find student loan garnishment data
            for garnishment in garnishment_data:
                if garnishment.get(GDK.TYPE, '').lower() == GT.STUDENT_DEFAULT_LOAN:
                    student_loan_garnishment = garnishment
                    break
            
            if isinstance(loan_amt, dict):
                if student_loan_garnishment:
                    cases = student_loan_garnishment.get(GDK.DATA, [])
                    for idx, (key, amount) in enumerate(loan_amt.items()):
                        case_id = cases[idx].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{idx}") if idx < len(cases) else f"{GRF.CASE_PREFIX}{idx}"
                        
                        if isinstance(amount, (int, float)):
                            withholding_amounts.append({GRF.AMOUNT: round(amount, 2), GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_ID: case_id})
                            total_student_loan_amt += amount
                        else:
                            withholding_amounts.append({GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_ID: case_id})
                else:
                    # Fallback to case_index if no garnishment data found
                    for idx, (key, amount) in enumerate(loan_amt.items()):
                        if isinstance(amount, (int, float)):
                            withholding_amounts.append({GRF.AMOUNT: round(amount, 2), GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_INDEX: idx})
                            total_student_loan_amt += amount
                        else:
                            withholding_amounts.append({GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN, GRF.CASE_INDEX: idx})
            elif isinstance(loan_amt, (int, float)):
                withholding_amounts.append({GRF.AMOUNT: round(loan_amt, 2), GRF.TYPE: GRF.STUDENT_LOAN})
                total_student_loan_amt = loan_amt
            else:
                withholding_amounts.append({GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.STUDENT_LOAN})

            if total_student_loan_amt <= 0:
                standardized_result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                standardized_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
            else:
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, total_student_loan_amt, garn_fees)
                garnishment_fees_amount = round(garnishment_fees, 2) if isinstance(garnishment_fees, (int, float)) else 0.0
                
                standardized_result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_student_loan_amt, 2)
                standardized_result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                standardized_result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(total_student_loan_amt + garnishment_fees_amount, 2)
                standardized_result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                standardized_result[CR.ER_DEDUCTION]["total_employer_cost"] = round(total_student_loan_amt + garnishment_fees_amount, 2)

            standardized_result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = withholding_amounts
            standardized_result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(result[CRK.DISPOSABLE_EARNING], 2)
            standardized_result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            standardized_result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = CM.NA
            standardized_result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = CM.NA
            
            return standardized_result
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} student loan: {e}")
            return self._create_standardized_result(GT.STUDENT_DEFAULT_LOAN, record, error_message=f"{EM.ERROR_CALCULATING} student loan: {e}")

    def calculate_state_tax_levy(self, record, config_data=None, garn_fees=None):
        """
        Calculate state tax levy garnishment with standardized result structure.
        """
        try:
            state_tax_view = StateTaxLevyCalculator()
            work_state = record.get(EE.WORK_STATE)
            calculation_result = state_tax_view.calculate(record, config_data[GT.STATE_TAX_LEVY])
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(record)
            
            if calculation_result == CommonConstants.NOT_FOUND:
                return self._create_standardized_result(GT.STATE_TAX_LEVY, record, error_message=f"State tax levy {EM.CONFIGURATION_NOT_FOUND}")
            
            # Create standardized result
            result = self._create_standardized_result(GT.STATE_TAX_LEVY, record)
            
            if isinstance(calculation_result, dict) and calculation_result.get(CR.WITHHOLDING_AMT, 0) <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.STATE_TAX_LEVY}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result.get(CR.DISPOSABLE_EARNING, 0), 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = round(calculation_result[CR.WITHHOLDING_AMT], 2)
                
                # Calculate garnishment fees
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, withholding_amount, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.STATE_TAX_LEVY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(withholding_amount + garnishment_fees_amount, 2)
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(withholding_amount + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} state tax levy: {e}")
            return self._create_standardized_result(GT.STATE_TAX_LEVY, record, error_message=f"{EM.ERROR_CALCULATING} state tax levy: {e}")

    def calculate_creditor_debt(self, record, config_data=None, garn_fees=None):
        """
        Calculate creditor debt garnishment with standardized result structure.
        """
        try:
            creditor_debt_calculator = CreditorDebtCalculator()
            work_state = record.get(EE.WORK_STATE)
            calculation_result = creditor_debt_calculator.calculate(record, config_data[GT.CREDITOR_DEBT])
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self._create_standardized_result(GT.CREDITOR_DEBT, record, error_message=f"Creditor debt {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self._create_standardized_result(GT.CREDITOR_DEBT, record, error_message=f"Creditor debt {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(record)
            
            # Create standardized result
            result = self._create_standardized_result(GT.CREDITOR_DEBT, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.CREDITOR_DEBT}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                # Calculate garnishment fees
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, withholding_amount, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.CREDITOR_DEBT}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(withholding_amount + garnishment_fees_amount, 2)
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(withholding_amount + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} creditor debt: {e}")
            return self._create_standardized_result(GT.CREDITOR_DEBT, record, error_message=f"{EM.ERROR_CALCULATING} creditor debt: {e}")
        
    def calculate_franchise_tax_board(self, record, config_data=None, garn_fees=None):
        """
        Calculate franchise tax board garnishment with standardized result structure.
        """
        try:
            creditor_debt_calculator = FranchaiseTaxBoard()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            calculation_result = creditor_debt_calculator.calculate(record, config_data[CDK.FRANCHISE_TAX_BOARD])
            
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self._create_standardized_result(GT.FRANCHISE_TAX_BOARD, record, error_message=f"Franchise tax board {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self._create_standardized_result(GT.FRANCHISE_TAX_BOARD, record, error_message=f"Franchise tax board {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Create standardized result
            result = self._create_standardized_result(GT.FRANCHISE_TAX_BOARD, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.FRANCHISE_TAX_BOARD}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                # Calculate garnishment fees
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, withholding_amount, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.FRANCHISE_TAX_BOARD}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(withholding_amount + garnishment_fees_amount, 2)
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(withholding_amount + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} franchise tax board: {e}")
            return self._create_standardized_result(GT.FRANCHISE_TAX_BOARD, record, error_message=f"{EM.ERROR_CALCULATING} franchise tax board: {e}")
        
    
    def calculate_bankruptcy(self, record, config_data=None, garn_fees=None):
        """
        Calculate bankruptcy garnishment with standardized result structure.
        """
        try:
            bankruptcy_calculator = Bankruptcy()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            calculation_result = bankruptcy_calculator.calculate(record, config_data[CDK.BANKRUPTCY])
            
            if isinstance(calculation_result, tuple):
                calculation_result = calculation_result[0]
                
            if calculation_result == CommonConstants.NOT_FOUND:
                return self._create_standardized_result(GT.BANKRUPTCY, record, error_message=f"Bankruptcy {EM.CONFIGURATION_NOT_FOUND}")
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                return self._create_standardized_result(GT.BANKRUPTCY, record, error_message=f"Bankruptcy {EM.GARNISHMENT_NOT_PERMITTED}")
                
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(payroll_taxes)
            
            # Create standardized result
            result = self._create_standardized_result(GT.BANKRUPTCY, record)
            
            if calculation_result[CR.WITHHOLDING_AMT] <= 0:
                result[GRF.CALCULATION_STATUS] = GRF.INSUFFICIENT_PAY
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: INSUFFICIENT_PAY, GRF.TYPE: GRF.BANKRUPTCY}
                ]
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = EM.GARNISHMENT_FEES_INSUFFICIENT_PAY
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            else:
                withholding_amount = max(round(calculation_result[CR.WITHHOLDING_AMT], 2), 0)
                
                # Calculate garnishment fees
                garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, withholding_amount, garn_fees)
                garnishment_fees_amount = 0.0
                
                if isinstance(garnishment_fees, (int, float)):
                    garnishment_fees_amount = round(garnishment_fees, 2)
                elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                    garnishment_fees_amount = round(float(garnishment_fees), 2)
                
                result[GRF.GARNISHMENT_DETAILS][GRF.WITHHOLDING_AMOUNTS] = [
                    {GRF.AMOUNT: withholding_amount, GRF.TYPE: GRF.BANKRUPTCY}
                ]
                result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = withholding_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(withholding_amount + garnishment_fees_amount, 2)
                
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(calculation_result[CR.DISPOSABLE_EARNING], 2)
                result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_BASIS] = calculation_result.get(CR.WITHHOLDING_BASIS, CM.NA)
                result[GRF.CALCULATION_METRICS][GRF.WITHHOLDING_CAP] = calculation_result.get(CR.WITHHOLDING_CAP, CM.NA)
                
                result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
                result[CR.ER_DEDUCTION]["total_employer_cost"] = round(withholding_amount + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} bankruptcy: {e}")
            return self._create_standardized_result(GT.BANKRUPTCY, record, error_message=f"{EM.ERROR_CALCULATING} bankruptcy: {e}")


    def calculate_ewot(self, record, config_data, garn_fees=None):
        """
        Calculate FTB EWOT/Court/Vehicle garnishment.
        """
        try:
            garnishment_data = record.get(EE.GARNISHMENT_DATA)
            if not garnishment_data:
                return None
            garnishment_type = garnishment_data[0].get(
                    EE.GARNISHMENT_TYPE, "").strip().lower()

            # Check if the config exists for this type
            if garnishment_type not in config_data:
                logger.error(f"Config data for '{garnishment_type}' is missing. Available keys: {list(config_data.keys())}")
                return {"error": f"{EM.CONFIG_DATA_MISSING} '{garnishment_type}' {EM.CONFIG_DATA_MISSING_END}"}

            creditor_debt_calculator = ftb_ewot()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            result = creditor_debt_calculator.calculate(
                record, config_data[garnishment_type]
            )
            if isinstance(result, tuple):
                result = result[0]
            if result == CommonConstants.NOT_FOUND:
                return None
            elif result == CommonConstants.NOT_PERMITTED:
                return CommonConstants.NOT_PERMITTED
            total_mandatory_deduction_val = ChildSupport(
                work_state
            ).calculate_md(payroll_taxes)
            if result[CR.WITHHOLDING_AMT] <= 0:
                return self._handle_insufficient_pay_garnishment(
                    record, result[CR.DISPOSABLE_EARNING], total_mandatory_deduction_val
                )
            else:
                record[CR.AGENCY] = [{CR.WITHHOLDING_AMT: [
                    {garnishment_type: max(round(result[CR.WITHHOLDING_AMT], 2), 0)}
                ]}]
                record[CR.DISPOSABLE_EARNING] = round(
                    result[CR.DISPOSABLE_EARNING], 2
                )
                record[CR.TOTAL_MANDATORY_DEDUCTION] = round(
                    total_mandatory_deduction_val, 2
                )
                record[CR.ER_DEDUCTION] = {
                    CR.GARNISHMENT_FEES: self.get_rounded_garnishment_fee(
                        work_state, record, result[CR.WITHHOLDING_AMT], garn_fees
                    )
                }
                record[CR.WITHHOLDING_LIMIT_RULE] = CommonConstants.WITHHOLDING_RULE_PLACEHOLDER
                record[CR.WITHHOLDING_BASIS] = result.get(CR.WITHHOLDING_BASIS)
                record[CR.WITHHOLDING_CAP] = result.get(CR.WITHHOLDING_CAP)
                return record
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} {garnishment_type}: {e}")
            return {"error": f"{EM.ERROR_CALCULATING} {garnishment_type}: {e}"}


    def calculate_child_support_priority(self, record, config_data=None,garn_fees=None):
        """
        Calculate creditor debt garnishment.
        """
        try:
            child_support_priority = WithholdingProcessor()
            payroll_taxes = record.get(PT.PAYROLL_TAXES)
            work_state = record.get(EE.WORK_STATE)
            result = child_support_priority.calculate(
                record)
            return result
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING} franchise tax board: {e}")
            return {"error": f"{EM.ERROR_CALCULATING} franchise tax board: {e}"}


    def calculate_multiple_garnishment(self, record, config_data=None, garn_fees=None):
        """
        Calculate multiple garnishment with standardized result structure.
        """
        try:
            # Create standardized result for multiple garnishment
            result = self._create_standardized_result("multiple_garnishment", record)
            result["garnishment_types"] = []
            
            # Prepare record for multiple garnishment calculation
            # The MultipleGarnishmentPriorityOrder expects garnishment_orders to be in the record
            prepared_record = record.copy()
            prepared_record[GDK.GARNISHMENT_ORDERS] = record.get(GDK.GARNISHMENT_ORDERS, [])
            
            multiple_garnishment = MultipleGarnishmentPriorityOrder(prepared_record, config_data)
            work_state = record.get(EE.WORK_STATE)
            calculation_result = multiple_garnishment.calculate()
            
            if calculation_result == CommonConstants.NOT_FOUND:
                result[GRF.CALCULATION_STATUS] = GRF.NOT_FOUND
                result[GRF.ERROR] = EM.NO_GARNISHMENT_CONFIGURATION
                return result
                
            elif calculation_result == CommonConstants.NOT_PERMITTED:
                result[GRF.CALCULATION_STATUS] = GRF.NOT_PERMITTED
                result[GRF.ERROR] = EM.GARNISHMENT_NOT_PERMITTED_CASE
                return result
            
            total_mandatory_deduction_val = ChildSupport(work_state).calculate_md(record.get(PT.PAYROLL_TAXES))
            total_withheld = 0.0
            
            # Process each garnishment type from the calculation results
            for garnishment_type, type_result in calculation_result.items():
                if isinstance(type_result, dict):
                    type_withholding_amounts = []
                    type_total_withheld = 0.0
                    
                    # Handle child support specific structure
                    if garnishment_type == GT.CHILD_SUPPORT:
                        result_amounts = type_result.get(CRK.RESULT_AMT, {})
                        arrear_amounts = type_result.get(CRK.ARREAR_AMT, {})
                        
                        # Get garnishment data from input to extract case IDs
                        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                        child_support_garnishment = None
                        
                        # Find child support garnishment data
                        for garnishment in garnishment_data:
                            if garnishment.get(GDK.TYPE, '').lower() == GT.CHILD_SUPPORT:
                                child_support_garnishment = garnishment
                                break
                        
                        if child_support_garnishment:
                            cases = child_support_garnishment.get(GDK.DATA, [])
                            result_amounts_list = list(result_amounts.values())
                            arrear_amounts_list = list(arrear_amounts.values())
                            
                            for i, (key, amount) in enumerate(result_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.CURRENT_SUPPORT,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                            
                            for i, (key, amount) in enumerate(arrear_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.ARREAR,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                        else:
                            # Fallback to case_index if no garnishment data found
                            for i, (key, amount) in enumerate(result_amounts.items()):
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.CURRENT_SUPPORT,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                            
                            for i, (key, amount) in enumerate(arrear_amounts.items()):
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.ARREAR,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                    
                    # Handle student loan specific structure
                    elif garnishment_type == GT.STUDENT_DEFAULT_LOAN:
                        student_loan_amounts = type_result.get(CRK.STUDENT_LOAN_AMT, {})
                        
                        # Get garnishment data from input to extract case IDs
                        garnishment_data = record.get(EE.GARNISHMENT_DATA, [])
                        student_loan_garnishment = None
                        
                        # Find student loan garnishment data
                        for garnishment in garnishment_data:
                            if garnishment.get(GDK.TYPE, '').lower() == GT.STUDENT_DEFAULT_LOAN:
                                student_loan_garnishment = garnishment
                                break
                        
                        if student_loan_garnishment:
                            cases = student_loan_garnishment.get(GDK.DATA, [])
                            for i, (key, amount) in enumerate(student_loan_amounts.items()):
                                case_id = cases[i].get(EE.CASE_ID, f"{GRF.CASE_PREFIX}{i}") if i < len(cases) else f"{GRF.CASE_PREFIX}{i}"
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.STUDENT_LOAN,
                                    GRF.CASE_ID: case_id
                                })
                                type_total_withheld += amount
                        else:
                            # Fallback to case_index if no garnishment data found
                            for i, (key, amount) in enumerate(student_loan_amounts.items()):
                                type_withholding_amounts.append({
                                    GRF.AMOUNT: round(amount, 2),
                                    GRF.TYPE: GRF.STUDENT_LOAN,
                                    GRF.CASE_INDEX: i
                                })
                                type_total_withheld += amount
                    
                    # Handle other garnishment types (creditor debt, etc.)
                    else:
                        withholding_amount = type_result.get(CR.WITHHOLDING_AMT, 0)
                        type_withholding_amounts.append({
                            GRF.AMOUNT: round(withholding_amount, 2),
                            GRF.TYPE: garnishment_type
                        })
                        type_total_withheld = withholding_amount
                    
                    # Add garnishment type to result
                    result[GRF.GARNISHMENT_TYPES].append({
                        GRF.GARNISHMENT_TYPE: garnishment_type,
                        GRF.WITHHOLDING_AMOUNTS: type_withholding_amounts,
                        GRF.TOTAL_WITHHELD: round(type_total_withheld, 2),
                        GRF.STATUS: type_result.get(GRF.CALCULATION_STATUS, 'processed'),
                        GRF.CALCULATION_METRICS: {
                            GRF.DISPOSABLE_EARNINGS: type_result.get(CRK.DE, 0),
                            GRF.ALLOWABLE_DISPOSABLE_EARNINGS: type_result.get(CRK.ADE, 0),
                            CRK.TWENTY_FIVE_PERCENT_OF_DE: type_result.get(CRK.TWENTY_FIVE_PERCENT_OF_DE, 0),
                            CRK.CURRENT_AMOUNT_WITHHELD: type_result.get(CRK.CURRENT_AMOUNT_WITHHELD, 0),
                            CRK.AMOUNT_LEFT_FOR_OTHER_GARN: type_result.get(CRK.AMOUNT_LEFT_FOR_OTHER_GARN, 0)
                        }
                    })
                    
                    total_withheld += type_total_withheld
                        
            # Calculate garnishment fees
            garnishment_fees = self.get_rounded_garnishment_fee(work_state, record, total_withheld, garn_fees)
            garnishment_fees_amount = 0.0
            
            if isinstance(garnishment_fees, (int, float)):
                garnishment_fees_amount = round(garnishment_fees, 2)
            elif isinstance(garnishment_fees, str) and garnishment_fees.replace('.', '').replace('-', '').isdigit():
                garnishment_fees_amount = round(float(garnishment_fees), 2)
            
            # Update garnishment details
            result[GRF.GARNISHMENT_DETAILS][GRF.TOTAL_WITHHELD] = round(total_withheld, 2)
            result[GRF.GARNISHMENT_DETAILS][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            result[GRF.GARNISHMENT_DETAILS][GRF.NET_WITHHOLDING] = round(total_withheld + garnishment_fees_amount, 2)
            
            # Update calculation metrics
            if GT.CHILD_SUPPORT in calculation_result:
                child_support_result = calculation_result[GT.CHILD_SUPPORT]
                result[GRF.CALCULATION_METRICS][GRF.DISPOSABLE_EARNINGS] = round(child_support_result.get(CRK.DE, 0), 2)
                result[GRF.CALCULATION_METRICS][GRF.ALLOWABLE_DISPOSABLE_EARNINGS] = round(child_support_result.get(CRK.ADE, 0), 2)
            
            result[GRF.CALCULATION_METRICS][GRF.TOTAL_MANDATORY_DEDUCTIONS] = round(total_mandatory_deduction_val, 2)
            
            # Update employer deductions
            result[CR.ER_DEDUCTION][GRF.GARNISHMENT_FEES] = garnishment_fees_amount
            result[CR.ER_DEDUCTION]["total_employer_cost"] = round(total_withheld + garnishment_fees_amount, 2)
            
            return result
            
        except Exception as e:
            logger.error(f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")
            return self._create_standardized_result("multiple_garnishment", record, error_message=f"{EM.ERROR_CALCULATING_MULTIPLE_GARNISHMENT} {e}")
                
    def calculate_garnishment_wrapper(self, record, config_data,garn_fees=None):
            """
            Wrapper function for parallel processing of garnishment calculations.
            """
            try:
                garnishment_data = record.get(EE.GARNISHMENT_DATA)
                if not garnishment_data:
                    return None
                garnishment_type = garnishment_data[0].get(
                    EE.GARNISHMENT_TYPE, "").strip().lower()
                result = self.calculate_garnishment(
                    garnishment_type, record, config_data,garn_fees)
                if result is None:
                    return CommonConstants.NOT_FOUND
                elif result == CommonConstants.NOT_PERMITTED:
                    return CommonConstants.NOT_PERMITTED
                else:
                    return result
            except Exception as e:
                logger.error(f"{EM.ERROR_IN_GARNISHMENT_WRAPPER} {e}")
                return {"error": f"{EM.ERROR_IN_GARNISHMENT_WRAPPER} {e}"}

    def calculate_garnishment_result(self, case_info,batch_id, config_data,garn_fees=None):
        """
        Calculates garnishment result for a single case.
        """
        try:
            state = StateAbbreviations(case_info.get(
                EE.WORK_STATE)).get_state_name_and_abbr()
            ee_id = case_info.get(EE.EMPLOYEE_ID)
            is_multiple_garnishment_type=case_info.get("is_multiple_garnishment_type")
            if is_multiple_garnishment_type ==True:
                calculated_result=self.calculate_multiple_garnishment(case_info,config_data,garn_fees)
            else:
                calculated_result = self.calculate_garnishment_wrapper(
                case_info, config_data,garn_fees)
            if isinstance(calculated_result, dict) and GRF.ERROR in calculated_result:
                return {
                    GRF.ERROR: calculated_result[GRF.ERROR],
                    "status_code": calculated_result.get("status_code", 500),
                    GRF.EMPLOYEE_ID: ee_id,
                    GRF.WORK_STATE: state
                }
            if calculated_result == CommonConstants.NOT_FOUND:
                return {
                    GRF.ERROR: f"Garnishment could not be calculated for employee {ee_id} because the state of {state} has not been implemented yet."
                }
            elif calculated_result == CommonConstants.NOT_PERMITTED:
                return {GRF.ERROR: f"In {state}, garnishment for creditor debt is not permitted."}
            elif not calculated_result:
                return {
                    GRF.ERROR: f"{EM.COULD_NOT_CALCULATE_GARNISHMENT} {ee_id}"
                }
            return calculated_result
        except Exception as e:
            logger.error(
                f"{EM.UNEXPECTED_ERROR} {case_info.get(EE.EMPLOYEE_ID)}: {e}")
            return {
                GRF.ERROR: f"{EM.UNEXPECTED_ERROR} {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"
            }

    def process_and_store_case(self, case_info, batch_id, config_data,garn_fees=None):
        try:
            with transaction.atomic():
                ee_id = case_info.get(EE.EMPLOYEE_ID)
                state = StateAbbreviations(case_info.get(
                    EE.WORK_STATE)).get_state_name_and_abbr().title()
                pay_period = case_info.get(EE.PAY_PERIOD).title()

                result = self.calculate_garnishment_result(
                    case_info, batch_id, config_data,garn_fees)

                withholding_basis = result.get(CR.WITHHOLDING_BASIS)
                withholding_cap = result.get(CR.WITHHOLDING_CAP)

                if isinstance(result, dict) and result.get(GRF.ERROR):
                    return result

                garnishment_type_data = result.get(EE.GARNISHMENT_DATA)
                
                # Process rules for all garnishment types (not just the first one)
                if garnishment_type_data:
                    for garnishment_group in garnishment_type_data:
                        garnishment_type = garnishment_group.get(GDK.TYPE, "").lower()
                        garnishment_data_list = garnishment_group.get(GDK.DATA, [])
                        
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
                if case_info.get(EE.GARNISHMENT_DATA):
                    first_group = case_info.get(EE.GARNISHMENT_DATA, [{}])[0]
                    first_case_data = first_group.get(GDK.DATA, [{}])
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

                result.pop(CR.WITHHOLDING_BASIS, None)  # Use None as default to avoid KeyError
                result.pop(CR.WITHHOLDING_CAP, None)
                return result
                
        except Exception as e:
            return {GRF.ERROR: f"{EM.ERROR_PROCESSING_CASE} {case_info.get(EE.EMPLOYEE_ID)}: {str(e)}"}

    def get_all_garnishment_types(self, cases_data: List[Dict]) -> Set[str]:
        """
        Extract all unique garnishment types from the cases data.
        Handles both single and multi-garnishment cases.
        """
        garnishment_types = set()
        
        logger.debug(f"Processing {len(cases_data)} cases for garnishment types")
        
        for i, case in enumerate(cases_data):
            logger.debug(f"Case {i} keys: {list(case.keys())}")
            garnishment_data = case.get(EE.GARNISHMENT_DATA, [])
            logger.debug(f"Case {i} garnishment_data: {garnishment_data}")
            
            for j, garnishment in enumerate(garnishment_data):
                logger.debug(f"Garnishment {j}: {garnishment}")
                garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get(GDK.TYPE)
                logger.debug(f"Extracted garnishment_type: {garnishment_type}")
                if garnishment_type:
                    normalized_type = garnishment_type.lower().strip()
                    garnishment_types.add(normalized_type)
                    logger.debug(f"Added normalized type: {normalized_type}")
                    
        logger.debug(f"Final garnishment_types: {garnishment_types}")
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
            garnishment_type = garnishment.get(EE.GARNISHMENT_TYPE) or garnishment.get(GDK.TYPE)
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