
from rest_framework import status
from django.conf import settings
from django.db.models import Q
from django.db import transaction
from datetime import date

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
from processor.models import MultipleGarnPriorityOrders
from processor.serializers  import MultipleGarnPriorityOrderCRUDSerializer
from processor.garnishment_library.utils.response import ResponseHelper
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
import logging
from user_app.constants import CalculationFields as CF

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
    DeductionPriorityCRUDSerializer,
)
from processor.models import WithholdingRules, WithholdingLimit, DeductionPriority, State
from django.db import transaction


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
    Supports effective date logic to automatically manage active/inactive records.
    """

    def get_queryset(self, rule_id=None, include_inactive=False):
        """
        Get queryset filtered by rule_id if provided.
        By default, only returns active limits with effective_date <= today or null.
        Set include_inactive=True to get all limits regardless of active status.
        """
        queryset = WithholdingLimit.objects.select_related('rule__state')
        
        # Apply effective date filtering unless include_inactive is True
        if not include_inactive:
            today = date.today()
            queryset = queryset.filter(
                is_active=True
            ).filter(Q(effective_date__isnull=True) | Q(effective_date__lte=today))
        
        if rule_id:
            try:
                queryset = queryset.filter(rule_id=int(rule_id))
            except ValueError:
                raise ValueError("rule_id must be an integer")
        
        return queryset

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
                queryset = self.get_queryset()
                rec = queryset.get(pk=pk)
                serializer = WithholdingLimitCRUDSerializer(rec)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            # Optional filter by rule_id
            rule_id = rule_id or request.query_params.get('rule_id')
            # Check for include_inactive query parameter
            include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
            qs = self.get_queryset(rule_id=rule_id, include_inactive=include_inactive)
            serializer = WithholdingLimitCRUDSerializer(qs, many=True)
            return ResponseHelper.success_response(
                message="All data fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except ValueError as e:
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
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


class DeductionPriorityAPIView(APIView):
    """
    CRUD API for DeductionPriority.
    Accepts state name/code and deduction name; stores related IDs.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("DeductionPriority fetched successfully"),
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def get(self, request, pk=None):
        try:
            if pk:
                rec = DeductionPriority.objects.select_related('state', 'deduction_type').get(pk=pk)
                serializer = DeductionPriorityCRUDSerializer(rec)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            qs = DeductionPriority.objects.select_related('state', 'deduction_type').all()
            serializer = DeductionPriorityCRUDSerializer(qs, many=True)
            return ResponseHelper.success_response(
                message="All data fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except DeductionPriority.DoesNotExist:
            return ResponseHelper.error_response("DeductionPriority not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in DeductionPriority GET")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=DeductionPriorityCRUDSerializer)
    def post(self, request, pk=None):
        try:
            if pk is not None:
                logger.warning("POST received with pk=%s; ignoring pk and proceeding with create", pk)
            serializer = DeductionPriorityCRUDSerializer(data=request.data)
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
            logger.exception("Error creating DeductionPriority")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=DeductionPriorityCRUDSerializer)
    def put(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = DeductionPriority.objects.get(pk=pk)
            serializer = DeductionPriorityCRUDSerializer(rec, data=request.data)
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
        except DeductionPriority.DoesNotExist:
            return ResponseHelper.error_response("DeductionPriority not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating DeductionPriority")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = DeductionPriority.objects.get(pk=pk)
            rec.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )
        except DeductionPriority.DoesNotExist:
            return ResponseHelper.error_response("DeductionPriority not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting DeductionPriority")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeductionPriorityReorderAPIView(APIView):
    """
    Move a DeductionPriority record to a new priority and reindex the sequence for the given state.
    Request body: { "id": <int>, "state": <name or code>, "new_priority": <int> }
    """

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Record ID to move'),
                'state': openapi.Schema(type=openapi.TYPE_STRING, description='State name or code'),
                'new_priority': openapi.Schema(type=openapi.TYPE_INTEGER, description='1-based new position'),
            },
            required=['id', 'state', 'new_priority']
        ),
        responses={200: 'Reordered successfully'}
    )
    def post(self, request):
        try:
            record_id = request.data.get('id')
            state_in = request.data.get('state') or request.data.get('state_name') or request.data.get('state_code')
            try:
                new_priority = int(request.data.get('new_priority'))
            except Exception:
                return ResponseHelper.error_response("new_priority must be an integer", status_code=status.HTTP_400_BAD_REQUEST)

            if not record_id or not state_in:
                return ResponseHelper.error_response("id and state are required", status_code=status.HTTP_400_BAD_REQUEST)

            # Resolve state
            state_obj = State.objects.filter(state__iexact=state_in).first() or \
                        State.objects.filter(state_code__iexact=state_in).first()
            if not state_obj:
                return ResponseHelper.error_response(f"State '{state_in}' not found", status_code=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                rec = DeductionPriority.objects.select_for_update().get(id=record_id)
                # Scope: all priorities for this state
                items = list(DeductionPriority.objects.select_for_update().filter(state=state_obj).order_by('priority_order', 'id'))
                # Ensure the record belongs to the same scope
                if rec.state_id != state_obj.id:
                    return ResponseHelper.error_response("Record does not belong to provided state", status_code=status.HTTP_400_BAD_REQUEST)

                # Bound new index
                new_index = max(0, min(new_priority - 1, len(items) - 1))
                # Rebuild order
                items = [i for i in items if i.id != rec.id]
                items.insert(new_index, rec)
                for idx, item in enumerate(items, start=1):
                    if item.priority_order != idx:
                        DeductionPriority.objects.filter(id=item.id).update(priority_order=idx)

            # Return updated order for the state
            updated = DeductionPriority.objects.filter(state=state_obj).order_by('priority_order', 'id').values('id', 'priority_order')
            return ResponseHelper.success_response(message="Reordered successfully", data={'order': list(updated)})
        except DeductionPriority.DoesNotExist:
            return ResponseHelper.error_response("DeductionPriority not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error reordering DeductionPriority")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    