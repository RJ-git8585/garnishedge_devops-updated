
from rest_framework import status
from django.conf import settings

from processor.garnishment_library.utils import StateAbbreviations, WLIdentifier
import os
import logging
import json
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg import openapi
from processor.garnishment_library.calculations.child_support import ChildSupportHelper
from drf_yasg.utils import swagger_auto_schema

logger = logging.getLogger(__name__)



class ChildSupportCalculationRules(APIView):
    """
    API view to get the withholding limit rule data for a specific state.
    Provides robust exception handling and clear response messages.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Withholding limit rule data retrieved successfully'),
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, state, employee_id, supports_2nd_family, arrears_of_more_than_12_weeks, de, no_of_order):
        """
        Retrieve the withholding limit rule data for a specific state and employee.
        """
        try:
            # Normalize state name
            state_name = StateAbbreviations(state).get_state_name_and_abbr()
            file_path = os.path.join(
                settings.BASE_DIR,
                'user_app',
                'configuration files/child support tables/withholding_rules.json'
            )

            # Read the JSON file
            with open(file_path, 'r') as file:
                data = json.load(file)

            ccpa_rules_data = data.get("WithholdingRules", [])
            # Find the record for the given state
            records = next(
                (rec for rec in ccpa_rules_data if rec['state'].lower() == state_name.lower()), None)

            if not records:
                return Response({
                    'success': False,
                    'message': 'State not found',
                    'status_code': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)

            # Determine DE > 145 logic
            try:
                de_gt_145 = "No" if float(de) <= 145 or records.get(
                    "rule") != "Rule_6" else "Yes"
            except Exception:
                de_gt_145 = "No"

            # Adjust arrears_of_more_than_12_weeks for Rule_4
            arrears_val = "" if records.get(
                "rule") == "Rule_4" else arrears_of_more_than_12_weeks

            # Determine order_gt_one logic for Rule_4
            try:
                order_gt_one = "No" if int(no_of_order) > 1 or records.get(
                    "rule") != "Rule_4" else "Yes"
            except Exception:
                order_gt_one = "No"

            # Identify withholding limit using state rules
            try:
                wl_limit = WLIdentifier().find_wl_value(
                    state_name, employee_id, supports_2nd_family, arrears_val, de_gt_145, order_gt_one
                )
                records["applied_withholding_limit"] = round(
                    wl_limit * 100, 0) if isinstance(wl_limit, (int, float)) else wl_limit
            except Exception as e:
                return Response({
                    "success": False,
                    "message": f"Error calculating withholding limit: {str(e)}",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Get mapping keys for mandatory deductions
            try:
                mapping_keys = ChildSupportHelper(state_name).get_mapping_keys()
                result = {}
                for item in mapping_keys:
                    key = item.split("_")[0]
                    result[key] = item
                records["mandatory_deductions"] = result
            except Exception as e:
                records["mandatory_deductions"] = {}
                # Optionally log this error

            response_data = {
                'success': True,
                'message': 'Data retrieved successfully',
                'status_code': status.HTTP_200_OK,
                'data': records
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # logger.error(f"Error in ChildSupportCalculationRules: {e}")
            return Response({
                "success": False,
                "message": f"Error retrieving child support calculation rules: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)