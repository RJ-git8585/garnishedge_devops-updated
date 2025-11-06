from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import traceback as t
from processor.services import CalculationDataView
from processor.garnishment_library.utils.response import ResponseHelper
from user_app.constants import (
    EmployeeFields as EE,
    BatchDetail
)
from processor.garnishment_library.calculations.multiple_garnishment import MultipleGarnishmentPriorityOrder
from datetime import datetime
from django.db.models import Prefetch
from user_app.models import EmployeeDetail, GarnishmentOrder
from garnishedge_project.model_audit import log_model_create
from typing import Dict, Set, List, Any

logger = logging.getLogger(__name__)


def _calculate_garnishment_worker(case_info, batch_id, config_data):
    """
    Worker function for processing garnishment calculations in separate threads.
    This function handles proper database connection management for threading.
    """
    from django.db import connections
    
    # Set up logging for worker thread
    worker_logger = logging.getLogger(f"{__name__}.worker")
    
    try:
        # Ensure we have a fresh database connection for this thread
        # Django automatically creates thread-local connections
        connections.close_all()
        
        worker_logger.debug(f"Worker thread started for employee {case_info.get(EE.EMPLOYEE_ID, 'N/A')}")
        
        # Create a new instance of CalculationDataView for this worker thread
        calculation_service = CalculationDataView()
        result = calculation_service.calculate_garnishment_result(case_info, batch_id, config_data)
        
        # Close database connections after processing to free up resources
        connections.close_all()
        
        worker_logger.debug(f"Worker thread completed for employee {case_info.get(EE.EMPLOYEE_ID, 'N/A')}")
        return result
        
    except Exception as e:
        worker_logger.error(f"Error in worker thread for employee {case_info.get(EE.EMPLOYEE_ID, 'N/A')}: {str(e)}", exc_info=True)
        # Close connections on error as well
        try:
            connections.close_all()
        except:
            pass
        return {
            "error": f"Error processing garnishment for employee {case_info.get(EE.EMPLOYEE_ID, 'N/A')}: {str(e)}",
            "status_code": 500,
            "employee_id": case_info.get(EE.EMPLOYEE_ID, 'N/A')
        }


class PostCalculationView(APIView):
    """Handles Garnishment Calculation API Requests with Multi-Type Support"""

    def _enrich_payroll_data_with_employee_info(self, cases_data):
        """
        Enriches payroll data with employee and garnishment information from the database.
        This method handles the new input format where only basic payroll data is provided.
        """
        enriched_cases = []
        not_found_employees = []

        for case in cases_data:
            ee_id = case.get('ee_id')
            
            if not ee_id:
                not_found_employees.append({
                    'not_found': 'N/A',
                    'message': 'ee_id is missing from case data'
                })
                continue

            try:
                # Fetch employee with related garnishment orders
                employee = EmployeeDetail.objects.filter(
                    is_active=True
                ).select_related(
                    'home_state', 'work_state', 'filing_status'
                ).prefetch_related(
                    Prefetch(
                        'garnishments',
                        queryset=GarnishmentOrder.objects.filter(
                            is_active=True
                        ).select_related(
                            'issuing_state', 'garnishment_type'
                        )
                    )
                ).get(ee_id__iexact=ee_id)

                # Build enriched case data
                enriched_case = self._build_enriched_case_from_employee(case, employee)
                enriched_cases.append(enriched_case)

            except EmployeeDetail.DoesNotExist:
                # Log missing employee and continue processing
                not_found_employees.append({
                    'not_found': ee_id,
                    'message': f'ee_id {ee_id} is not found in the records'
                })

        return enriched_cases, not_found_employees

    def _extract_deductions_from_garnishment_orders(self, garnishment_orders, case_data=None):
        """
        Extract and aggregate deduction details from garnishment orders.
        Sums up values across all garnishment orders for the employee.
        Falls back to case data for fields not available in garnishment orders.
        """
        deductions = {
            'current_child_support': 0,
            'current_medical_support': 0,
            'current_spousal_support': 0,
            'medical_support_arrear': 0,
            'spousal_support_arrear': 0,
            'fees': 0,
            'child_support_arrear': 0,
            'house_payment': 0,
            'insurance_payment': 0,
            'remaining_child_support_arrear': 0,
            'remaining_spousal_support_arrear': 0
        }
        
        for garnishment in garnishment_orders:
            # Sum up deduction values from all garnishment orders
            if garnishment.garnishment_type.type.lower() == "spousal_and_medical_support":
                deductions['current_child_support'] = float(garnishment.current_child_support or 0)
                deductions['child_support_arrear'] = float(garnishment.child_support_arrear or 0)
                deductions['current_medical_support'] = float(garnishment.current_medical_support or 0)
                deductions['current_spousal_support'] = float(garnishment.current_spousal_support or 0)
                deductions['medical_support_arrear'] = float(garnishment.medical_support_arrear or 0)
                deductions['spousal_support_arrear'] = float(garnishment.spousal_support_arrear or 0)
                deductions['fees'] += float(garnishment.garnishment_fees or 0)
            else:
                deductions['current_child_support'] = float(0)
                deductions['current_medical_support'] = float(0)
                deductions['current_spousal_support'] = float(0)
                deductions['medical_support_arrear'] = float(0)
                deductions['spousal_support_arrear'] = float(0)
                deductions['child_support_arrear'] = float(0)
                deductions['fees'] += float(0)
        
        # For fields not available in GarnishmentOrder model, try to get from case data
        if case_data:
            deductions['house_payment'] = case_data.get('house_payment', 0)
            deductions['insurance_payment'] = case_data.get('insurance_payment', 0)
            deductions['remaining_child_support_arrear'] = case_data.get('remaining_child_support_arrear', 0)
            deductions['remaining_spousal_support_arrear'] = case_data.get('remaining_spousal_support_arrear', 0)
        
        logger.debug(f"Extracted deductions from garnishment orders: {deductions}")
        return deductions

    def _build_enriched_case_from_employee(self, case, employee):
        """
        Build enriched case data by merging employee and garnishment information.
        """
        # Get garnishment orders grouped by type
        garnishment_orders = employee.garnishments.all()
        garnishment_data = {}
        garnishment_types = []

        logger.debug(f"Employee {employee.ee_id} has {garnishment_orders.count()} garnishment orders")
        for garnishment in garnishment_orders:
            garn_type = garnishment.garnishment_type.type
            logger.debug(f"Processing garnishment type: {garn_type}")
            if garn_type not in garnishment_data:
                garnishment_data[garn_type] = []
                garnishment_types.append(garn_type)
            
            garnishment_data[garn_type].append({
                EE.CASE_ID: garnishment.case_id,
                'ordered_amount': float(garnishment.ordered_amount),
                'arrear_amount': float(garnishment.arrear_amount) if garnishment.arrear_amount else 0.0
            })

        # Build garnishment data structure
        garnishment_data_list = []
        for garn_type in garnishment_types:
            garnishment_data_list.append({
                'type': garn_type,
                'data': garnishment_data[garn_type]
            })
        
        logger.debug(f"Built garnishment_data_list: {garnishment_data_list}")

        # Check if employee has any garnishment orders
        if not garnishment_data_list:
            logger.info(f"Employee {employee.ee_id} has no garnishment orders - will enrich with empty garnishment data")

        # Get the first garnishment order for some fields (issuing_state, etc.)
        first_garnishment = garnishment_orders.first()
        # print("first_garnishment",first_garnishment[0])

        # Build enriched case - merge original case data with employee data
        enriched_case = case.copy()  # Start with original case data
        
        # Extract deductions from garnishment orders
        deductions = self._extract_deductions_from_garnishment_orders(garnishment_orders, case)

        # Add employee-specific fields
        enriched_case.update({
            'work_state': employee.work_state.state if employee.work_state else None,
            'home_state': employee.home_state.state if employee.home_state else None,
            'issuing_state': first_garnishment.issuing_state.state_code.lower() if first_garnishment and first_garnishment.issuing_state else None,
            'no_of_exemption_including_self': employee.number_of_exemptions,
            'garnishment_fees':  first_garnishment.garnishment_fees if first_garnishment and first_garnishment.garnishment_fees else 0,
            'is_multiple_garnishment_type': len(garnishment_types) > 1,
            'no_of_student_default_loan': employee.number_of_student_default_loan,
            'filing_status': employee.filing_status.name if employee.filing_status else None,
            'statement_of_exemption_received_date': first_garnishment.received_date.strftime('%m-%d-%Y') if first_garnishment and first_garnishment.received_date else None,
            'garn_start_date': first_garnishment.start_date.strftime('%m-%d-%Y') if first_garnishment and first_garnishment.start_date else None,
            'non_consumer_debt': (not first_garnishment.is_consumer_debt) if first_garnishment else False,
            'consumer_debt': first_garnishment.is_consumer_debt if first_garnishment else False,
            'support_second_family': employee.support_second_family,
            'no_of_dependent_child': employee.number_of_dependent_child,
            'arrears_greater_than_12_weeks': first_garnishment.arrear_greater_than_12_weeks if first_garnishment else False,
            'deductions': deductions,
            'garnishment_data': garnishment_data_list,
            'garnishment_orders': garnishment_types
        })
        print("enriched_case",enriched_case)
        return enriched_case

    def post(self, request, *args, **kwargs):
        # Get user for audit logging
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        
        try:
            batch_id = request.data.get(BatchDetail.BATCH_ID)
            cases_data = request.data.get("payroll_data", [])
        except ParseError:
            return Response(
                {
                    "error": "Invalid JSON body. Send 'Content-Type: application/json' with 'batch_id' and 'payroll_data'."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Input validation
        if not batch_id:
            # Log validation error
            try:
                log_model_create(
                    model_name="GarnishmentCalculation",
                    object_id="VALIDATION_ERROR",
                    user=user,
                    new_values={
                        "status": "VALIDATION_ERROR",
                        "error": "batch_id is required",
                        "processed_at": datetime.now().isoformat()
                    }
                )
            except:
                pass
            return Response(
                {"error": "batch_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if not cases_data:
            # Log validation error
            try:
                log_model_create(
                    model_name="GarnishmentCalculation",
                    object_id=str(batch_id),
                    user=user,
                    new_values={
                        "batch_id": batch_id,
                        "status": "VALIDATION_ERROR",
                        "error": "No PayRoll Data provided",
                        "processed_at": datetime.now().isoformat()
                    }
                )
            except:
                pass
            return Response(
                {"error": "No PayRoll Data provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if this is the new payroll input format (has client_id, payroll_date, etc.)
        # vs the old enriched format (has garnishment_data, work_state, etc.)
        is_payroll_input = any('client_id' in case and 'payroll_date' in case for case in cases_data)
        
        if is_payroll_input:
            # New payroll input format - enrich with employee data
            logger.info(f"Processing payroll input format for batch {batch_id}")
            enriched_cases, not_found_employees = self._enrich_payroll_data_with_employee_info(cases_data)
            
            if not enriched_cases:
                # All employees not found
                if not_found_employees:
                    return ResponseHelper.error_response(
                        message="No employees found",
                        error=not_found_employees[0],
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    return Response(
                        {"error": "No valid cases to process"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            cases_data = enriched_cases

            
            # Log any missing employees but continue processing
            if not_found_employees:
                logger.warning(f"Some employees not found in batch {batch_id}: {[emp['not_found'] for emp in not_found_employees]}")
        else:
            # Old enriched input format - use as is
            logger.info(f"Processing enriched input format for batch {batch_id}")
            not_found_employees = []

        output = []
        calculation_service = CalculationDataView()
        try:
            # Debug: Print the structure of enriched cases
            logger.debug("First case structure:")
            if cases_data:
                logger.debug(f"Keys in first case: {list(cases_data[0].keys())}")
                logger.debug(f"Garnishment data in first case: {cases_data[0].get('garnishment_data', 'NOT FOUND')}")
                logger.debug(f"Garnishment orders in first case: {cases_data[0].get('garnishment_orders', 'NOT FOUND')}")
            
            # Step 1: Extract all unique garnishment types across all cases
            all_garnishment_types = calculation_service.get_all_garnishment_types(cases_data)
            logger.info(f"Extracted garnishment types: {all_garnishment_types}")
            
            if not all_garnishment_types:
                # Check if this is because employees have no garnishment orders
                if is_payroll_input:
                    return Response(
                        {
                            "success": True,
                            "message": "Batch processed successfully - no garnishment orders found for any employees",
                            "status_code": status.HTTP_200_OK,
                            "batch_id": batch_id,
                            "processed_at": datetime.now(),
                            "summary": {
                                "total_cases": len(cases_data),
                                "successful_cases": 0,
                                "failed_cases": 0,
                                "garnishment_types_processed": [],
                                "missing_employees": len(not_found_employees) if not_found_employees else 0
                            },
                            "results": [],
                            "not_found_employees": not_found_employees if not_found_employees else []
                        }, 
                        status=status.HTTP_200_OK
                    )
                else:
                    return Response(
                        {"error": "No valid garnishment types found in the input data"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            logger.info(f"Processing batch {batch_id} with garnishment types: {all_garnishment_types}")

            #Step 2: Preload garnishment fees for all types
            # gar_fees= calculation_service.preload_garnishment_fees()

            # Step 3: Preload configuration data for all required types
            full_config_data = calculation_service.preload_config_data(all_garnishment_types)
            
            
            if not full_config_data:
                logger.warning(f"No configuration data loaded for types: {all_garnishment_types}")

            # Step 4: Process each case with appropriate configuration
            # Use ThreadPoolExecutor for concurrent processing with Django
            # Threads work better with Django ORM than processes
            max_workers = min(50, len(cases_data) + 10)  # Dynamic workers, cap at 50
            
            # Create executor with threading
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_case = {}
                
                for case_info in cases_data:
                    # Determine if this is a multi-garnishment case
                    is_multi_case = calculation_service.is_multi_garnishment_case(case_info)
                    
                    if is_multi_case:
                        # For multi-garnishment cases, get case-specific types
                        case_types = calculation_service.get_case_garnishment_types(case_info)
                        case_config = calculation_service.filter_config_for_case(full_config_data, case_types)
                        
                        logger.debug(f"Multi-garnishment case detected for employee {case_info.get(EE.EMPLOYEE_ID, 'N/A')}: {case_types}")
                    else:
                        # For single garnishment cases, use full config (it will be filtered naturally)
                        case_config = full_config_data
                    
                    # Submit case for processing using the worker function
                    future = executor.submit(
                        _calculate_garnishment_worker, 
                        case_info, 
                        batch_id, 
                        case_config
                    )
                    future_to_case[future] = case_info

                # Step 5: Collect results
                from concurrent.futures import TimeoutError as FuturesTimeoutError
                
                for future in as_completed(future_to_case, timeout=300):  # 5 minute timeout per task
                    case_info_original = future_to_case[future]
                    ee_id_for_log = case_info_original.get(EE.EMPLOYEE_ID, "N/A")
                    
                    try:
                        result = future.result(timeout=10)  # 10 second timeout for result retrieval
                        if result:
                            # Add metadata for multi-garnishment cases
                            if calculation_service.is_multi_garnishment_case(case_info_original):
                                result['is_multi_garnishment'] = True
                                # Only set garnishment_types if it's not already populated with detailed breakdown
                                if not result.get('garnishment_types') or len(result.get('garnishment_types', [])) == 0:
                                    result['garnishment_types'] = list(
                                        calculation_service.get_case_garnishment_types(case_info_original)
                                    )
                            
                            output.append(result)
                        else:
                            logger.warning(f"No result returned for employee {ee_id_for_log}")
                            
                    except FuturesTimeoutError as e:
                        error_message = f"Timeout processing garnishment for employee {ee_id_for_log}"
                        logger.error(error_message, exc_info=True)
                        
                        output.append({
                            "employee_id": ee_id_for_log,
                            "error": error_message,
                            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
                        })
                    except Exception as e:
                        error_message = f"Error processing garnishment for employee {ee_id_for_log}: {str(e)}"
                        logger.error(error_message, exc_info=True)
                        
                        output.append({
                            "employee_id": ee_id_for_log,
                            "error": error_message,
                            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
                        })

        except Exception as e:
            logger.error(f"Critical error in batch processing {batch_id}: {str(e)}", exc_info=True)
            
            # Log failed calculation to audit trail
            try:
                log_model_create(
                    model_name="GarnishmentCalculation",
                    object_id=str(batch_id) if batch_id else "UNKNOWN",
                    user=user,
                    new_values={
                        "batch_id": batch_id if batch_id else "UNKNOWN",
                        "status": "FAILED",
                        "error": str(e),
                        "processed_at": datetime.now().isoformat()
                    }
                )
            except Exception as audit_error:
                logger.warning(f"Failed to log calculation audit: {audit_error}")
            
            return Response(
                {"error": f"Critical error during batch processing: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 6: Prepare response
        error_count = sum(1 for item in output if "error" in item)
        success_count = len(output) - error_count

        if error_count == len(output) and output:
            # All cases failed
            return ResponseHelper.error_response(
                'All cases failed during processing.',
                output,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        elif error_count > 0:
            # Partial success
            logger.warning(f"Batch {batch_id}: {success_count} successful, {error_count} failed")
            
        # Prepare response data
        response_data = {
            "success": True,
            "message": "Batch processed successfully." ,
            "status_code": status.HTTP_200_OK,
            "batch_id": batch_id,
            "processed_at": datetime.now(),
            "summary": {
                "total_cases": len(cases_data),
                "successful_cases": success_count,
                "failed_cases": error_count,
                "garnishment_types_processed": list(all_garnishment_types)
            },
            "results": output
        }
        
        # Add missing employees info if processing payroll input
        if is_payroll_input and not_found_employees:
            response_data["not_found_employees"] = not_found_employees
            response_data["summary"]["missing_employees"] = len(not_found_employees)
        
        # Log calculation to audit trail
        try:
            # Extract case IDs from cases_data
            case_ids = [case.get(EE.CASE_ID, 'N/A') for case in cases_data[:10]]  # First 10 case IDs only
            
            log_model_create(
                model_name="GarnishmentCalculation",
                object_id=str(batch_id),
                user=user,
                new_values={
                    "batch_id": batch_id,
                    "case_ids": case_ids,
                    "total_cases": len(cases_data),
                    "successful_cases": success_count,
                    "failed_cases": error_count,
                    "garnishment_types": list(all_garnishment_types),
                    "processed_at": datetime.now().isoformat(),
                    "employee_ids": [case.get(EE.EMPLOYEE_ID, 'N/A') for case in cases_data[:10]]  # First 10 IDs only
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to log calculation audit: {audit_error}")
        
        return Response(response_data, status=status.HTTP_200_OK)

