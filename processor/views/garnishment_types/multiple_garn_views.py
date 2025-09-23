from processor.models import MultipleGarnPriorityOrders
from processor.serializers.shared_serializers import MultipleGarnPriorityOrderCRUDSerializer
from processor.garnishment_library.utils.response import ResponseHelper
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
import logging

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