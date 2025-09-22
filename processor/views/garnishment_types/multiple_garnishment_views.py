from rest_framework import status
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import logging

from processor.models import MultipleGarnPriorityOrders, State, GarnishmentType
from processor.serializers.multiple_garnishment_serializers import MultipleGarnPriorityOrderCRUDSerializer
from processor.garnishment_library.utils.response import ResponseHelper
from django.db import transaction

logger = logging.getLogger(__name__)


class MultipleGarnPriorityOrderAPIView(APIView):
    """
    CRUD API for MultipleGarnPriorityOrders.
    Accepts state name/code and garnishment type name; stores related IDs.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("MultipleGarnPriorityOrders fetched successfully"),
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def get(self, request, pk=None):
        try:
            if pk:
                rec = MultipleGarnPriorityOrders.objects.select_related('state', 'garnishment_type').get(pk=pk)
                serializer = MultipleGarnPriorityOrderCRUDSerializer(rec)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            qs = MultipleGarnPriorityOrders.objects.select_related('state', 'garnishment_type').all()
            serializer = MultipleGarnPriorityOrderCRUDSerializer(qs, many=True)
            return ResponseHelper.success_response(
                message="All data fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except MultipleGarnPriorityOrders.DoesNotExist:
            return ResponseHelper.error_response("MultipleGarnPriorityOrders not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in MultipleGarnPriorityOrders GET")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=MultipleGarnPriorityOrderCRUDSerializer)
    def post(self, request):
        try:
            serializer = MultipleGarnPriorityOrderCRUDSerializer(data=request.data)
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
            logger.exception("Error creating MultipleGarnPriorityOrders")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=MultipleGarnPriorityOrderCRUDSerializer)
    def put(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = MultipleGarnPriorityOrders.objects.get(pk=pk)
            serializer = MultipleGarnPriorityOrderCRUDSerializer(rec, data=request.data)
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
        except MultipleGarnPriorityOrders.DoesNotExist:
            return ResponseHelper.error_response("MultipleGarnPriorityOrders not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating MultipleGarnPriorityOrders")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rec = MultipleGarnPriorityOrders.objects.get(pk=pk)
            rec.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )
        except MultipleGarnPriorityOrders.DoesNotExist:
            return ResponseHelper.error_response("MultipleGarnPriorityOrders not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting MultipleGarnPriorityOrders")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MultipleGarnPriorityOrderReorderAPIView(APIView):
    """
    Move a MultipleGarnPriorityOrders record to a new priority and reindex the sequence for the given state.
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
                rec = MultipleGarnPriorityOrders.objects.select_for_update().get(id=record_id)
                # Scope: all priorities for this state (across all garnishment types)
                items = list(MultipleGarnPriorityOrders.objects.select_for_update().filter(state=state_obj).order_by('priority_order', 'id'))
                
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
                        MultipleGarnPriorityOrders.objects.filter(id=item.id).update(priority_order=idx)

            # Return updated order for the state
            updated = MultipleGarnPriorityOrders.objects.filter(state=state_obj).order_by('priority_order', 'id').values('id', 'priority_order')
            return ResponseHelper.success_response(message="Reordered successfully", data={'order': list(updated)})
        except MultipleGarnPriorityOrders.DoesNotExist:
            return ResponseHelper.error_response("MultipleGarnPriorityOrders not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error reordering MultipleGarnPriorityOrders")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
