
from rest_framework import status
from django.conf import settings

from processor.garnishment_library.utils import StateAbbreviations, WLIdentifier
from processor.garnishment_library.utils.response import ResponseHelper
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


from processor.serializers.child_support_serializers import (
    WithholdingRulesCRUDSerializer,
    WithholdingLimitCRUDSerializer,
)
from processor.models import WithholdingRules, WithholdingLimit


class WithholdingRulesAPIView(APIView):
    """
    CRUD API for WithholdingRules.
    Accepts state name/code as input; stores related State id; returns state name.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("WithholdingRules fetched successfully"),
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def get(self, request, pk=None):
        try:
            if pk:
                rule = WithholdingRules.objects.select_related('state').get(pk=pk)
                serializer = WithholdingRulesCRUDSerializer(rule)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            rules = WithholdingRules.objects.select_related('state').all()
            serializer = WithholdingRulesCRUDSerializer(rules, many=True)
            return ResponseHelper.success_response(
                message="All data fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except WithholdingRules.DoesNotExist:
            return ResponseHelper.error_response("WithholdingRules not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in WithholdingRules GET")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=WithholdingRulesCRUDSerializer)
    def post(self, request):
        try:
            serializer = WithholdingRulesCRUDSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error creating WithholdingRules")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=WithholdingRulesCRUDSerializer)
    def put(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule = WithholdingRules.objects.get(pk=pk)
            serializer = WithholdingRulesCRUDSerializer(rule, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except WithholdingRules.DoesNotExist:
            return ResponseHelper.error_response("WithholdingRules not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating WithholdingRules")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule = WithholdingRules.objects.get(pk=pk)
            rule.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )
        except WithholdingRules.DoesNotExist:
            return ResponseHelper.error_response("WithholdingRules not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting WithholdingRules")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithholdingLimitAPIView(APIView):
    """
    CRUD API for WithholdingLimit.
    Accepts state name/code and rule_number to resolve FK to WithholdingRules.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("WithholdingLimit fetched successfully"),
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def get(self, request, pk=None, rule_id=None):
        try:
            if pk:
                rec = WithholdingLimit.objects.select_related('rule__state').get(pk=pk)
                serializer = WithholdingLimitCRUDSerializer(rec)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            # Optional filter by rule_id
            rule_id = rule_id or request.query_params.get('rule_id')
            qs = WithholdingLimit.objects.select_related('rule__state').all()
            if rule_id:
                try:
                    qs = qs.filter(rule_id=int(rule_id))
                except ValueError:
                    return ResponseHelper.error_response(
                        message="rule_id must be an integer",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            serializer = WithholdingLimitCRUDSerializer(qs, many=True)
            return ResponseHelper.success_response(
                message="All data fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except WithholdingLimit.DoesNotExist:
            return ResponseHelper.error_response("WithholdingLimit not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in WithholdingLimit GET")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=WithholdingLimitCRUDSerializer)
    def post(self, request):
        try:
            serializer = WithholdingLimitCRUDSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error creating WithholdingLimit")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=WithholdingLimitCRUDSerializer)
    def put(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = WithholdingLimit.objects.get(pk=pk)
            serializer = WithholdingLimitCRUDSerializer(rec, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except WithholdingLimit.DoesNotExist:
            return ResponseHelper.error_response("WithholdingLimit not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating WithholdingLimit")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = WithholdingLimit.objects.get(pk=pk)
            rec.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )
        except WithholdingLimit.DoesNotExist:
            return ResponseHelper.error_response("WithholdingLimit not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting WithholdingLimit")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)