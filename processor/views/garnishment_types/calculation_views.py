from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import traceback as t
from processor.services.calculation_service import CalculationDataView
from processor.garnishment_library.utils.response import ResponseHelper
from user_app.constants import (
    EmployeeFields as EE,
    BatchDetail
)
from processor.garnishment_library.calculations.multiple_garnishment import MultipleGarnishmentPriorityOrder
from datetime import datetime


import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from typing import Dict, Set, List, Any

logger = logging.getLogger(__name__)

class PostCalculationView(APIView):
    """Handles Garnishment Calculation API Requests with Multi-Type Support"""

    def post(self, request, *args, **kwargs):
        batch_id = request.data.get(BatchDetail.BATCH_ID)
        cases_data = request.data.get("cases", [])

        # Input validation
        if not batch_id:
            return Response(
                {"error": "batch_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if not cases_data:
            return Response(
                {"error": "No cases provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        output = []
        calculation_service = CalculationDataView()

        try:
            # Step 1: Extract all unique garnishment types across all cases
            all_garnishment_types = calculation_service.get_all_garnishment_types(cases_data)
            
            if not all_garnishment_types:
                return Response(
                    {"error": "No valid garnishment types found in the input data"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Processing batch {batch_id} with garnishment types: {all_garnishment_types}")

            # Step 2: Preload configuration data for all required types
            full_config_data = calculation_service.preload_config_data(all_garnishment_types)
            
            if not full_config_data:
                logger.warning(f"No configuration data loaded for types: {all_garnishment_types}")

            # Step 3: Process each case with appropriate configuration
            with ThreadPoolExecutor(max_workers=100) as executor:
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
                    
                    # Submit case for processing
                    future = executor.submit(
                        calculation_service.process_and_store_case, 
                        case_info, 
                        batch_id, 
                        case_config
                    )
                    future_to_case[future] = case_info

                # Step 4: Collect results
                for future in as_completed(future_to_case):
                    case_info_original = future_to_case[future]
                    ee_id_for_log = case_info_original.get(EE.EMPLOYEE_ID, "N/A")
                    
                    try:
                        result = future.result()
                        if result:
                            # Add metadata for multi-garnishment cases
                            if calculation_service.is_multi_garnishment_case(case_info_original):
                                result['is_multi_garnishment'] = True
                                result['garnishment_types'] = list(
                                    calculation_service.get_case_garnishment_types(case_info_original)
                                )
                            
                            output.append(result)
                        else:
                            logger.warning(f"No result returned for employee {ee_id_for_log}")
                            
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
            return Response(
                {"error": f"Critical error during batch processing: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 5: Prepare response
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
            
        return Response({
            "success": True,
            "message": "Batch processed successfully." ,
            "status_code": status.HTTP_200_OK,
            "batch_id": batch_id,
            "processed_at":datetime.now(),
            "summary": {
                "total_cases": len(cases_data),
                "successful_cases": success_count,
                "failed_cases": error_count,
                "garnishment_types_processed": list(all_garnishment_types)
            },
            "results": output
        }, status=status.HTTP_200_OK)

