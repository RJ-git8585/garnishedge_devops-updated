import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import traceback as t
from processor.garnishment_library.calculations import  MultipleChild,AllocationMethodResolver
from processor.garnishment_library.utils import  AllocationMethods,StateAbbreviations
from processor.garnishment_library.utils.child_support import Helper
from user_app.constants import CalculationFields
from processor.models import ChildSupportPriority
from processor.serializers import PriorityDeductionSerializer
from processor.garnishment_library.input_validator import WithholdingInputValidator, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WithholdingDeductionError(Exception):
    """Base exception for withholding deduction errors."""
    pass

class PriorityOrderError(WithholdingDeductionError):
    """Raised when there is an error fetching or processing priority order."""
    pass

class StateNotFoundError(WithholdingDeductionError):
    """Raised when a state's priority order is not found."""
    pass


class InvalidDataError(WithholdingDeductionError):
    """Raised when input data is invalid."""
    pass


class DeductionType(Enum):
    """Enumeration of deduction types with standardized naming."""
    CURRENT_CHILD_SUPPORT = "current_child_support"
    CURRENT_MEDICAL_SUPPORT = "current_medical_support"
    CURRENT_SPOUSAL_SUPPORT = "current_spousal_support"
    MEDICAL_SUPPORT_ARREAR = "medical_support_arrear"
    SPOUSAL_SUPPORT_ARREAR = "spousal_support_arrear"
    FEES = "fees"
    CHILD_SUPPORT_ARREAR = "child_support_arrear"
    HOUSE_PAYMENT = "house_payment"
    INSURANCE_PAYMENT = "insurance_payment"
    REMAINING_CHILD_SUPPORT_ARREAR = "remaining_child_support_arrear"
    REMAINING_SPOUSAL_SUPPORT_ARREAR = "remaining_spousal_support_arrear"


@dataclass
class DeductionResult:
    """Represents the result of a deduction calculation."""
    deduction_type: DeductionType
    requested_amount: Decimal
    deducted_amount: Decimal
    remaining_balance: Decimal
    
    @property
    def is_fully_deducted(self) -> bool:
        """Check if the full requested amount was deducted."""
        return self.deducted_amount >= self.requested_amount


@dataclass
class EmployeeRecord:
    """Comprehensive employee record for withholding calculations."""
    cid: str
    eeid: str
    work_state: str
    employee_name: str
    support_second_family: bool
    arrears_greater_than_12_weeks: bool
    gross_pay: Decimal
    federal_tax: Decimal
    social_security_tax: Decimal
    medicare_tax: Decimal
    local_tax: Decimal
    state_tax: Decimal

    # Earnings details
    wages: Decimal = Decimal("0")
    commission_and_bonus: Decimal = Decimal("0")
    non_accountable_allowances: Decimal = Decimal("0")

    # Payroll taxes (fixed: should be Decimal, not dict)
    payroll_taxes: List[Dict[str, Any]] = field(default_factory=list)

    # Garnishment Data (fixed: proper type annotation)
    garnishment_data: List[Dict[str, Any]] = field(default_factory=list)
    
    # Support order details
    current_child_support: Decimal = Decimal("0")
    past_due_child_support: Decimal = Decimal("0")
    current_medical_support: Decimal = Decimal("0")
    past_due_medical_support: Decimal = Decimal("0")
    current_spousal_support: Decimal = Decimal("0")
    past_due_spousal_support: Decimal = Decimal("0")
    insurance_premiums: Decimal = Decimal("0")
    court_fee: Decimal = Decimal("0")
    
    # Additional deduction types from DeductionType enum
    house_payment: Decimal = Decimal("0")
    
    # Additional priority types to match DeductionType enum
    medical_support_arrears: Decimal = Decimal("0")
    spousal_support_arrears: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    child_support_arrear: Decimal = Decimal("0")
    medical_support_arrear: Decimal = Decimal("0")
    spousal_support_arrear: Decimal = Decimal("0")
    insurance_payment: Decimal = Decimal("0")
    remaining_child_support_arrear: Decimal = Decimal("0")
    remaining_spousal_support_arrear: Decimal = Decimal("0")
    
    # Calculated fields
    disposable_earnings: Decimal = field(init=False, default=Decimal("0"))
    allowable_disposable_earnings: Decimal = field(init=False, default=Decimal("0"))
    amount_ordered_withheld: Decimal = field(init=False, default=Decimal("0"))
    withholding_amount: Decimal = field(init=False, default=Decimal("0"))
    ade: Decimal = field(init=False, default=Decimal("0"))  
    tcsa: Decimal = field(init=False, default=Decimal("0"))
    taa: Decimal = field(init=False, default=Decimal("0"))
    twa: Decimal = field(init=False, default=Decimal("0")) 
    wa: Decimal = field(init=False, default=Decimal("0"))  
    alloc_method: AllocationMethods = field(init=False, default=AllocationMethods.PRORATE)


    def __post_init__(self):
        """Calculate derived fields after initialization."""
        
        try:
            # Extract tax values from payroll_taxes dictionary
            self._extract_tax_values()
            
            self.CSH = MultipleChild(self.work_state)
            self._calculate_allowable_disposable_earnings()
            self._calculate_amount_ordered_withheld()
            self._calculate_withholding_amount()
        except Exception as e:
            logger.error(f"Error in EmployeeRecord post_init: {e}")
            raise WithholdingDeductionError(f"Failed to initialize employee record: {e}")
    
    def _extract_tax_values(self) -> None:
        """Extract individual tax values from payroll_taxes dictionary."""
        try:
            if isinstance(self.payroll_taxes, dict):
                self.federal_tax = Decimal(str(self.payroll_taxes.get('federal_income_tax', 0)))
                self.social_security_tax = Decimal(str(self.payroll_taxes.get('social_security_tax', 0)))
                self.medicare_tax = Decimal(str(self.payroll_taxes.get('medicare_tax', 0)))
                self.local_tax = Decimal(str(self.payroll_taxes.get('local_tax', 0)))
                self.state_tax = Decimal(str(self.payroll_taxes.get('state_tax', 0)))
            else:
                # If payroll_taxes is not a dict, keep default values
                pass
        except Exception as e:
            logger.error(f"Error extracting tax values: {e}")
            # Keep default values if extraction fails
        
    def _calculate_allowable_disposable_earnings(self) -> None:
        """Calculate allowable disposable earnings using your existing functions."""
        try:
            # Fixed: Added missing issuing_state parameter
            issuing_state = self.work_state  # Assuming issuing state is same as employee state
            
            gross_pay = self.CSH.calculate_gross_pay(
                self.wages, self.commission_and_bonus, self.non_accountable_allowances
            )
            # Convert payroll_taxes dict to list format expected by calculate_md

            mandatory_deductions = self.CSH.calculate_md(self.payroll_taxes)
            disposable_earnings = self.CSH.calculate_de(gross_pay, mandatory_deductions)
            
            withholding_limit = self.CSH.calculate_wl(
                self.eeid, self.support_second_family, self.arrears_greater_than_12_weeks,
                disposable_earnings, self.garnishment_data, issuing_state
            )
            print(self.garnishment_data,"garnishment_data")
            
            self.ade = self.CSH.calculate_ade(disposable_earnings, withholding_limit)
            self.tcsa = self.CSH._support_amount(self.garnishment_data, CalculationFields.ORDERED_AMOUNT)
            self.taa = self.CSH._support_amount(self.garnishment_data, CalculationFields.ARREAR_AMOUNT)
            self.twa = sum(self.tcsa + self.taa)
            self.wa = min(self.ade,sum(self.tcsa))
            
            # Set disposable earnings for compatibility
            self.disposable_earnings = disposable_earnings
            self.allowable_disposable_earnings = self.ade
            
            self.alloc_method = AllocationMethodResolver(self.work_state).get_allocation_method()
            
        except Exception as e:
            print(t.print_exc())
            logger.error(f"Error calculating allowable disposable earnings: {e}")
            raise WithholdingDeductionError(f"ADE calculation failed: {e}")
    
    def _extract_garnishment_data_amounts(self) -> Tuple[Decimal, Decimal]:
        """Extract current_child_support and child_support_arrear from garnishment_data."""
        total_current_child_support = Decimal("0")
        total_child_support_arrear = Decimal("0")
        
        for garnishment_group in self.garnishment_data:
            if garnishment_group.get('type') == 'child_support_priority':
                for case_data in garnishment_group.get('data', []):
                    # Extract current_child_support from case data
                    current_support = case_data.get('current_child_support', 0)
                    if current_support:
                        total_current_child_support += Decimal(str(current_support))
                    
                    # Extract child_support_arrear from case data
                    child_arrear = case_data.get('child_support_arrear', 0)
                    if child_arrear:
                        total_child_support_arrear += Decimal(str(child_arrear))
        
        return total_current_child_support, total_child_support_arrear

    def _calculate_amount_ordered_withheld(self) -> None:
        """Calculate total amount ordered to be withheld."""
        try:
            # Extract amounts from garnishment data if available
            garnishment_current_support, garnishment_child_arrear = self._extract_garnishment_data_amounts()
            
            # Use garnishment data values if available, otherwise use record values
            current_child_support_amount = garnishment_current_support if garnishment_current_support > 0 else self.current_child_support
            child_support_arrear_amount = garnishment_child_arrear if garnishment_child_arrear > 0 else self.child_support_arrear
            
            self.amount_ordered_withheld = (
                current_child_support_amount +
                self.current_medical_support +
                self.current_spousal_support +
                child_support_arrear_amount +
                self.medical_support_arrear +
                self.spousal_support_arrear +
                self.fees +
                self.house_payment +
                self.insurance_payment +
                self.remaining_child_support_arrear +
                self.remaining_spousal_support_arrear
            )

        except Exception as e:
            logger.error(f"Error calculating amount ordered withheld: {e}")
            raise WithholdingDeductionError(f"AOW calculation failed: {e}")
    
    def _calculate_withholding_amount(self) -> None:
        """Calculate actual withholding amount (minimum of ADE and AOW)."""
        try:
            print("ade",self.ade)
            print("amount_ordered_withheld",self.amount_ordered_withheld)
            self.withholding_amount = min(self.ade, self.amount_ordered_withheld)
            print()
        except Exception as e:
            print(t.print_exc())
            logger.error(f"Error calculating withholding amount: {e}")
            raise WithholdingDeductionError(f"Withholding amount calculation failed: {e}")


class CurrentSupportCalculator:
    """Calculator for current support calculations."""
    
    def __init__(self, employee_record: EmployeeRecord):
        """Initialize calculator with employee record."""
        self.record = employee_record
    
    def calculate_ordered(self) -> Decimal:
        """Calculate current support amount based on complex business rules."""
        try:
            tcsa=self.record.tcsa
            twa=self.record.twa
            gross_pay=self.record.gross_pay
            withholding_amount=self.record.withholding_amount
            print("tcsa",tcsa)
            print("adewwww",withholding_amount)

            if self.record.withholding_amount <= 0:
                return Decimal("0")
            elif self.record.withholding_amount >= sum(tcsa) :
                print("hii")
                return self.record.CSH._calculate_each_amount(tcsa,"child support amount") 
            else:
                print("hello")
                if self.record.alloc_method == AllocationMethods.PRORATE:
                    # Prorate support amounts
                    cs_amounts = {
                        f"child support amount{i+1}": round((Decimal(str(amt)) / Decimal(str(twa))) * withholding_amount, 2) if gross_pay > 0 else 0
                        for i, amt in enumerate(tcsa)
                    }
                    return cs_amounts

                elif self.record.alloc_method == AllocationMethods.DEVIDEEQUALLY:
                    # Divide equally among orders
                    split_amt = round(self.record.ade / len(tcsa), 2) if tcsa else 0
                    print("split_amt",split_amt)
                    cs_amounts = {f"child support amount{i+1}": split_amt if gross_pay > 0 else 0
                        for i in range(len(tcsa))
                    }
                    return cs_amounts
                else:
                    raise ValueError(
                        "Invalid allocation method for garnishment.")
                
        except Exception as e:
            print(t.print_exc())
            raise ValueError(f"Error in CurrentSupportCalculator.calculate_ordered: {str(e)}")

    def calculate_arrear(self) -> Decimal:
        try:

            tcsa=self.record.tcsa
            gross_pay=self.record.gross_pay
            ade=self.record._calculate_withholding_amount()
            taa=self.record.taa
            print("taa",taa)
            wa=self.record.wa
            if self.record.withholding_amount <= 0:
                return Decimal("0")
            elif self.record.withholding_amount >= sum(taa) :
                return self.record.CSH._calculate_each_amount(taa,"arrear amount") 
            else:
                if self.record.alloc_method == AllocationMethods.PRORATE:
                    arrear_pool = wa - sum(tcsa)
                    total_arrears = sum(taa)
                    # Prorate arrear amounts
                    ar_amounts = {
                        f"arrear amount{i+1}": (
                            round((amt / total_arrears) * arrear_pool, 2)
                            if total_arrears and arrear_pool > 0 and gross_pay > 0 else 0
                        ) for i, amt in enumerate(taa)
                    }
                    return ar_amounts 
                elif self.record.alloc_method == AllocationMethods.DEVIDEEQUALLY:
                    # Divide equally among orders
                    arrear_pool = self.record.ade - sum(taa)
                    ar_amounts = {
                        f"arrear amount{i+1}": round(amt / len(taa), 2) if arrear_pool > 0 and gross_pay > 0 else 0
                        for i, amt in enumerate(taa)
                    }
                    return ar_amounts
                else:
                    raise ValueError(
                        "Invalid allocation method for garnishment.")
        except Exception as e:
            print(t.print_exc())
            raise ValueError(f"Error in CurrentSupportCalculator.calculate_arrear: {str(e)}")


class PriorityOrderRepository:
    """Repository for managing state priority orders."""
    
    def __init__(self, state_id: Optional[str] = None):
        """Initialize repository with optional state_id."""
        self.state_id = state_id
    
    def _get_priority(self) -> List[Dict[str, Any]]:
        try:
            work_state_name = StateAbbreviations(self.state_id).get_state_name_and_abbr()
            if not work_state_name:
                raise ValueError("Could not resolve state name from abbreviation.")
            
            pri_order_qs = ChildSupportPriority.objects.select_related('state', 'deduction_type').filter(
                state__state__iexact=work_state_name
            ).order_by('priority_order')
            
            if not pri_order_qs.exists():
                logger.warning(f"No priority order found for state: {self.work_state}")
                return []
                
            serializer = PriorityDeductionSerializer(pri_order_qs, many=True)
            return serializer.data
            
        except Exception as e:
            logger.error(f"Error in ChildSupportPriority.get_priority: {str(e)}\n{t.format_exc()}")
            logger.error(f"Failed to fetch priority order for state '{self.state_id}': {e}")
            raise PriorityOrderError(f"Database error fetching priority order for {self.state_id}.") from e


class WithholdingProcessor:
    """Main processor for withholding deductions."""
    
    def __init__(
        self, 
        priority_repository: Optional[PriorityOrderRepository] = None,
        validator: Optional[WithholdingInputValidator] = None
    ):
        """Initialize processor with dependencies."""
        self.priority_repository = priority_repository
        self.validator = validator or WithholdingInputValidator()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def calculate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process withholding deductions from input data.
        
        Args:
            input_data: Dictionary containing employee and deduction data
            
        Returns:
            Dictionary containing processing results and deduction details
        """
        try:
            # Validate input using separated validation module
            validated_data = self.validator.validate(input_data)
            
            # Parse and create employee record
            record = self._create_employee_record(validated_data)
            
            # Initialize priority repository with state info
            if not self.priority_repository:
                self.priority_repository = PriorityOrderRepository(state_id=record.work_state)
            else:
                self.priority_repository.state_id = record.work_state
            
            # Get state priority order
            priority_order = self.priority_repository._get_priority()
            
            # Process deductions according to priority
            deduction_results = self._process_deductions_by_priority(record, priority_order)
            
            # Generate summary
            summary = self._generate_summary(record, deduction_results)
            
            self.logger.info(f"Successfully processed withholding for employee {record.eeid}")
            
            return {
                "success": True,
                "employee_info": {
                    "cid": record.cid,
                    "eeid": record.eeid,
                    "work_state": record.work_state,
                },
                "calculations": {
                    "gross_pay": float(record.gross_pay),
                    "disposable_earnings": float(record.disposable_earnings),
                    "allowable_disposable_earnings": round(float(record.allowable_disposable_earnings), 1),
                    "amount_ordered_withheld": float(record.amount_ordered_withheld),
                    "total_withholding_amount": float(record.withholding_amount)
                },
                "deduction_details": deduction_results,
                # "priority_processing": {
                #     "total_priorities_available": len(priority_order),
                #     "priorities_processed": len(deduction_results),
                #     "priorities_skipped": len(priority_order) - len(deduction_results),
                #     "priority_order": [
                #         {
                #             "order": i + 1,
                #             "deduction_type": item.get('type', str(item)) if isinstance(item, dict) else str(item),
                #             "state": item.get('state', '') if isinstance(item, dict) else '',
                #             "processed": i < len(deduction_results)
                #         }
                #         for i, item in enumerate(priority_order)
                #     ]
                # },
                "summary": summary
            }
            
        except ValidationError as e:
            self.logger.error(f"Input validation failed: {e}")
            return {
                "success": False,
                "error": f"Input validation failed: {e}",
                "error_type": "ValidationError"
            }
        except Exception as e:
            self.logger.error(f"Error processing withholding: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    @staticmethod
    def _get_deduction_value(data: Dict[str, Any], field_name: str, default_value: Any = None) -> Any:
        """
        Helper method to get deduction values from either the new nested structure 
        or the old flat structure for backward compatibility.
        
        Args:
            data: The validated data dictionary
            field_name: Name of the field to retrieve
            default_value: Default value if field is not found
            
        Returns:
            The field value from deductions object or direct access
        """
        # First try to get from the new nested deductions structure
        deductions = data.get('deductions', {})
        if deductions and field_name in deductions:
            return deductions[field_name]
        
        # Fallback to direct access for backward compatibility
        return data.get(field_name, default_value)

    def _create_employee_record(self, validated_data: Dict[str, Any]) -> EmployeeRecord:
        """Create EmployeeRecord from validated data."""
        try:
            return EmployeeRecord(
                cid=str(validated_data.get('batch_id', '')),  
                eeid=str(validated_data['ee_id']),
                work_state=str(validated_data['work_state']).strip(),
                employee_name=str(validated_data.get('ee_id', 'Unknown')),  
                support_second_family=bool(validated_data.get('support_second_family', False)),
                arrears_greater_than_12_weeks=bool(validated_data.get('arrears_greater_than_12_weeks', False)),
                gross_pay=validated_data['gross_pay'],
                federal_tax=Decimal("0"),  
                social_security_tax=Decimal("0"),  
                medicare_tax=Decimal("0"),  
                local_tax=Decimal("0"),  
                state_tax=Decimal("0"),  
                wages=validated_data.get('wages', Decimal("0")),
                commission_and_bonus=validated_data.get('commission_and_bonus', Decimal("0")),
                non_accountable_allowances=validated_data.get('non_accountable_allowances', Decimal("0")),
                payroll_taxes=validated_data.get('payroll_taxes', {}),
                garnishment_data=validated_data.get('garnishment_data', []),
                current_child_support=self._get_deduction_value(validated_data, 'current_child_support', Decimal("0")),
                current_medical_support=self._get_deduction_value(validated_data, 'current_medical_support', Decimal("0")),
                current_spousal_support=self._get_deduction_value(validated_data, 'current_spousal_support', Decimal("0")),
                child_support_arrear=self._get_deduction_value(validated_data, 'child_support_arrear', validated_data.get('child_support_arrear', Decimal("0"))),
                medical_support_arrear=self._get_deduction_value(validated_data, 'medical_support_arrear', validated_data.get('medical_support_arrear', Decimal("0"))),
                insurance_payment=self._get_deduction_value(validated_data, 'insurance_payment', validated_data.get('insurance_payment', Decimal("0"))),
                house_payment=self._get_deduction_value(validated_data, 'house_payment', validated_data.get('house_payment', Decimal("0"))),
                spousal_support_arrear=self._get_deduction_value(validated_data, 'spousal_support_arrear', Decimal("0")),
                fees=self._get_deduction_value(validated_data, 'fees', validated_data.get('fees', Decimal("0"))),
                remaining_child_support_arrear=validated_data.get('remaining_child_support_arrear', Decimal("0")),
                remaining_spousal_support_arrear=validated_data.get('remaining_spousal_support_arrear', Decimal("0"))
            )
        except Exception as e:
            print(t.print_exc())
            logger.error(f"Error creating employee record: {e}")
            raise InvalidDataError(f"Failed to create employee record: {e}")
    
    def _process_child_support_cases(
        self,
        record: EmployeeRecord,
        deduction_type: DeductionType,
        cs_calculator: 'CurrentSupportCalculator',
        remaining_withholding: Decimal,
        priority_order: int
    ) -> List[Dict[str, Any]]:
        """Process individual child support cases instead of aggregating them."""
        results = []
        
        try:
            # Get the individual case amounts from garnishment data
            garnishment_cases = []
            for garnishment_group in record.garnishment_data:
                if garnishment_group.get('type') == 'child_support_priority':
                    garnishment_cases = garnishment_group.get('data', [])
                    break
            
            if not garnishment_cases:
                # Fallback to calculator if no garnishment data
                if deduction_type == DeductionType.CURRENT_CHILD_SUPPORT:
                    cs_amounts = cs_calculator.calculate_ordered()
                else:  # CHILD_SUPPORT_ARREAR
                    arrear_amounts = cs_calculator.calculate_arrear()
                    cs_amounts = arrear_amounts
                
                if isinstance(cs_amounts, dict):
                    for i, (key, amount) in enumerate(cs_amounts.items()):
                        case_id = f"CALCULATOR_CASE_{i+1}"  # Prefix to distinguish from garnishment data cases
                        requested_amount = Decimal(str(amount))
                        deduction_amount = min(remaining_withholding, requested_amount)
                        
                        remaining_withholding = Decimal(str(remaining_withholding))
                        deduction_amount = Decimal(str(deduction_amount))
                        remaining_withholding -= deduction_amount
                        
                        result = {
                            "deduction_type": deduction_type.value,
                            "priority_order": priority_order,
                            "case_id": case_id,
                            "ordered_amount": float(requested_amount),
                            "deducted_amount": float(deduction_amount),
                            "remaining_balance": float(Decimal(str(requested_amount)) - Decimal(str(deduction_amount))),
                            "fully_deducted": deduction_amount >= requested_amount,
                            "source": "calculator_fallback"
                        }
                        results.append(result)
                return results
            
            # Process each individual case from garnishment data
            for i, case_data in enumerate(garnishment_cases):
                case_id = case_data.get('case_id', f'CASE_{i+1}')
                
                if deduction_type == DeductionType.CURRENT_CHILD_SUPPORT:
                    requested_amount = Decimal(str(case_data.get('current_child_support', 0)))
                else:  # CHILD_SUPPORT_ARREAR
                    requested_amount = Decimal(str(case_data.get('child_support_arrear', 0)))
                
                if requested_amount <= 0:
                    # Add zero amount result for tracking
                    result = {
                        "deduction_type": deduction_type.value,
                        "priority_order": priority_order,
                        "case_id": case_id,
                        "ordered_amount": 0.0,
                        "deducted_amount": 0.0,
                        "remaining_balance": 0.0,
                        "fully_deducted": True,
                        "skipped": True,
                        "reason": "No amount requested for this case"
                    }
                    results.append(result)
                    continue
                
                # Calculate actual deduction amount for this case
                deduction_amount = min(remaining_withholding, requested_amount)
                
                # Ensure both values are Decimal for consistent arithmetic
                remaining_withholding = Decimal(str(remaining_withholding))
                deduction_amount = Decimal(str(deduction_amount))
                remaining_withholding -= deduction_amount
                
                # Create individual case result
                result = {
                    "deduction_type": deduction_type.value,
                    "priority_order": priority_order,
                    "case_id": case_id,
                    "ordered_amount": float(requested_amount),
                    "deducted_amount": float(deduction_amount),
                    "remaining_balance": float(Decimal(str(requested_amount)) - Decimal(str(deduction_amount))),
                    "fully_deducted": deduction_amount >= requested_amount,
                    "source": "garnishment_data"
                }
                
                results.append(result)
                
                # If no more withholding available, break
                if remaining_withholding <= 0:
                    break
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing child support cases: {e}")
            # Return a single error result
            return [{
                "deduction_type": deduction_type.value,
                "priority_order": priority_order,
                "case_id": "ERROR",
                "ordered_amount": 0.0,
                "deducted_amount": 0.0,
                "remaining_balance": 0.0,
                "fully_deducted": False,
                "error": str(e)
            }]

    def _process_deductions_by_priority(
        self, 
        record: EmployeeRecord, 
        priority_order: List[str]
    ) -> List[Dict[str, Any]]:
        """Process deductions according to priority order."""
        results = []
        remaining_withholding = Decimal(str(record.withholding_amount))
        processed_deduction_types = set()  
        
        # Create current support calculator
        cs_calculator = CurrentSupportCalculator(record)
        
        for priority_item in priority_order:
            if remaining_withholding <= 0:
                break
            
            try:
                # Handle both string and dictionary priority formats
                if isinstance(priority_item, dict):
                    priority_type = priority_item.get('type', '')
                    db_priority_order = priority_item.get('priority_order', 0)
                else:
                    priority_type = str(priority_item)
                    db_priority_order = 0  # Fallback if not a dict
                
                # Convert string to DeductionType enum
                deduction_type = self._get_deduction_type(priority_type)
                print("deduction_type",deduction_type)
                if not deduction_type:
                    continue
                
                # Skip if this deduction type has already been processed
                if deduction_type.value in processed_deduction_types:
                    continue
                
                # Mark this deduction type as processed
                processed_deduction_types.add(deduction_type.value)
                
                # Handle child support cases individually
                if deduction_type in [DeductionType.CURRENT_CHILD_SUPPORT, DeductionType.CHILD_SUPPORT_ARREAR]:
                    child_results = self._process_child_support_cases(
                        record, deduction_type, cs_calculator, remaining_withholding, db_priority_order
                    )
                    
                    # Update remaining withholding based on total deducted from all child cases
                    total_deducted = sum(child_result.get("deducted_amount", 0) for child_result in child_results)
                    remaining_withholding = Decimal(str(remaining_withholding)) - Decimal(str(total_deducted))
                    
                    results.extend(child_results)
                else:
                    # Handle other deduction types as before
                    requested_amount = self._get_deduction_amount(record, deduction_type, cs_calculator)
                    print("remaining_withholdingrequested_amount",requested_amount)
                    print("requested_amount",requested_amount)
                    
                    if requested_amount <= 0:
                        # Still add to results with 0 amounts for tracking
                        result = {
                            "deduction_type": deduction_type.value,
                            "priority_order": db_priority_order,
                            "ordered_amount": 0.0,
                            "deducted_amount": 0.0,
                            "remaining_balance": 0.0,
                            "fully_deducted": False,
                            "skipped": True,
                            "reason": "No amount requested"
                        }
                        results.append(result)
                        continue
                    
                    
                    # Calculate actual deduction amount
                    deduction_amount = min(remaining_withholding, requested_amount)
                    # Ensure both values are Decimal for consistent arithmetic
                    remaining_withholding = Decimal(str(remaining_withholding))
                    deduction_amount = Decimal(str(deduction_amount))
                    remaining_withholding -= deduction_amount
                    
                    # Create deduction result
                    result = {
                        "deduction_type": deduction_type.value,
                        "priority_order": db_priority_order,
                        "ordered_amount": float(requested_amount),
                        "deducted_amount": float(deduction_amount),
                        "remaining_balance": float(Decimal(str(requested_amount)) - Decimal(str(deduction_amount))),
                        "fully_deducted": deduction_amount >= requested_amount
                    }
                    
                    results.append(result)
                
                # Only log for non-child support cases since child support cases are logged individually
                if deduction_type not in [DeductionType.CURRENT_CHILD_SUPPORT, DeductionType.CHILD_SUPPORT_ARREAR]:
                    self.logger.debug(f"Processed {deduction_type.value}: "
                                    f"${deduction_amount} of ${requested_amount} requested")
            except Exception as e:
                print(t.print_exc())
                self.logger.error(f"Error processing priority {priority_type}: {e}")

                failed_result = {
                    "deduction_type": priority_type,
                    "priority_order": db_priority_order if isinstance(priority_item, dict) else 0,
                    "ordered_amount": 0.0,
                    "deducted_amount": 0.0,
                    "remaining_balance": 0.0,
                    "fully_deducted": False,
                    "error": str(e)
                }
                results.append(failed_result)
                continue
        
        # Add information about skipped deductions that weren't processed due to insufficient funds
        for priority_item in priority_order:
            if isinstance(priority_item, dict):
                priority_type = priority_item.get('type', '')
                db_priority_order = priority_item.get('priority_order', 0)
            else:
                priority_type = str(priority_item)
                db_priority_order = 0
            
            deduction_type = self._get_deduction_type(priority_type)
            if deduction_type and deduction_type.value not in processed_deduction_types:
                skipped_result = {
                    "deduction_type": deduction_type.value,
                    "priority_order": db_priority_order,
                    "ordered_amount": 0.0,
                    "deducted_amount": 0.0,
                    "remaining_balance": 0.0,
                    "fully_deducted": False,
                    "skipped": True,
                    "reason": "Insufficient withholding amount remaining"
                }
                results.append(skipped_result)
        
        return results
    
    def _get_deduction_type(self, priority_string: str) -> Optional[DeductionType]:
        """Convert priority string to DeductionType enum."""
        # Mapping from database strings to enum values
        priority_mapping = {
            "current_child_support": DeductionType.CURRENT_CHILD_SUPPORT,
            "current_medical_support": DeductionType.CURRENT_MEDICAL_SUPPORT,
            "current_spousal_support": DeductionType.CURRENT_SPOUSAL_SUPPORT,
            "medical_support_arrear": DeductionType.MEDICAL_SUPPORT_ARREAR,
            "spousal_support_arrear": DeductionType.SPOUSAL_SUPPORT_ARREAR,
            "fees": DeductionType.FEES,
            "child_support_arrear": DeductionType.CHILD_SUPPORT_ARREAR,
            "house_payment": DeductionType.HOUSE_PAYMENT,
            "insurance_payment": DeductionType.INSURANCE_PAYMENT,
            "remaining_child_support_arrear": DeductionType.REMAINING_CHILD_SUPPORT_ARREAR,
            "remaining_spousal_support_arrear": DeductionType.REMAINING_SPOUSAL_SUPPORT_ARREAR,
        }
        
        return priority_mapping.get(priority_string)
    
    def _get_deduction_amount(
        self, 
        record: EmployeeRecord, 
        deduction_type: DeductionType,
        cs_calculator: CurrentSupportCalculator
    ) -> Decimal:
        """Get the deduction amount for a specific type."""
        try:
            if deduction_type in [ DeductionType.CURRENT_CHILD_SUPPORT]:
                # Use calculator for current support
                cs_amounts = cs_calculator.calculate_ordered()
                print("cs_amounts",cs_amounts)
                if isinstance(cs_amounts, dict):
                    return Decimal(str(sum(cs_amounts.values())))
                return Decimal(str(cs_amounts))
            
            elif deduction_type in [DeductionType.CHILD_SUPPORT_ARREAR, DeductionType.REMAINING_CHILD_SUPPORT_ARREAR]:
                # Use calculator for arrears
                arrear_amounts = cs_calculator.calculate_arrear()
                if isinstance(arrear_amounts, dict):
                    return Decimal(str(sum(arrear_amounts.values())))
                return Decimal(str(arrear_amounts))
            
            # Direct mapping for other deduction types
            deduction_mapping = {
                DeductionType.CURRENT_MEDICAL_SUPPORT: record.current_medical_support,
                DeductionType.CURRENT_SPOUSAL_SUPPORT: record.current_spousal_support,
                DeductionType.MEDICAL_SUPPORT_ARREAR: record.medical_support_arrear,
                DeductionType.SPOUSAL_SUPPORT_ARREAR: record.spousal_support_arrear,
                DeductionType.REMAINING_SPOUSAL_SUPPORT_ARREAR: record.remaining_spousal_support_arrear,
                DeductionType.REMAINING_CHILD_SUPPORT_ARREAR: record.remaining_child_support_arrear,
                DeductionType.FEES: record.fees,
                DeductionType.INSURANCE_PAYMENT: record.insurance_payment,
                DeductionType.HOUSE_PAYMENT: record.house_payment,
            }
            
            return deduction_mapping.get(deduction_type, Decimal("0"))
            
        except Exception as e:
            self.logger.error(f"Error getting deduction amount for {deduction_type}: {e}")
            return Decimal("0")
    
    def _generate_summary(
        self, 
        record: EmployeeRecord, 
        deduction_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate processing summary."""
        try:
            total_deducted = sum(result["deducted_amount"] for result in deduction_results)
            total_requested = sum(result["ordered_amount"] for result in deduction_results)
            
            # Convert to Decimal for proper calculation
            total_deducted_decimal = Decimal(str(total_deducted))
            total_requested_decimal = Decimal(str(total_requested))
            
            return {
                "total_requested": float(total_requested),
                "total_deducted": float(total_deducted),
                "remaining_allowable": round(float(Decimal(str(record.allowable_disposable_earnings)) - total_deducted_decimal), 1),
                "deduction_efficiency": float(
                    (total_deducted_decimal / total_requested_decimal * 100) if total_requested_decimal > 0 else 0
                ),
                "priorities_processed": len(deduction_results),
                "fully_satisfied_deductions": len([r for r in deduction_results if r["fully_deducted"]]),
                
            }
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return {
                "total_requested": 0.0,
                "total_deducted": 0.0,
                "remaining_allowable": 0.0,
                "deduction_efficiency": 0.0,
                "priorities_processed": 0,
                "fully_satisfied_deductions": 0
            }

