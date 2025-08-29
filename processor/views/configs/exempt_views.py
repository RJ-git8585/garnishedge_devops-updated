from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from processor.models import ExemptConfig
from processor.serializers import ExemptConfigWithThresholdSerializer
import logging
from rest_framework.views import APIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.exceptions import ValidationError

from processor.models import ThresholdCondition
from processor.serializers import ThresholdConditionSerializer
from processor.garnishment_library import ResponseHelper
import logging

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

class ExemptConfigAPIView(APIView):
    """
    API view for CRUD operations on ExemptConfig
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("ExemptConfig data fetched successfully", ExemptConfigWithThresholdSerializer(many=True)),
            404: "ExemptConfig not found",
            500: "Internal server error"
        }
    )
    def get(self, request, pk=None):
        try:
            if pk:
                config = ExemptConfig.objects.get(pk=pk)
                serializer = ExemptConfigWithThresholdSerializer(config)
                return Response(serializer.data, status=status.HTTP_200_OK)
            configs = ExemptConfig.objects.select_related('state','pay_period','garnishment_type').all()
            serializer = ExemptConfigWithThresholdSerializer(configs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ExemptConfig.DoesNotExist:
            return Response({"error": "ExemptConfig not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def post(self, request):
        try:
            serializer = ExemptConfigWithThresholdSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating ExemptConfig")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def put(self, request, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            config = ExemptConfig.objects.get(pk=pk)
            serializer = ExemptConfigWithThresholdSerializer(config, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ExemptConfig.DoesNotExist:
            return Response({"error": "ExemptConfig not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating ExemptConfig")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            config = ExemptConfig.objects.get(pk=pk)
            config.delete()
            return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
        except ExemptConfig.DoesNotExist:
            return Response({"error": "ExemptConfig not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting ExemptConfig")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdConditionAPI(APIView):
    """
    CRUD API for ThresholdCondition
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Threshold conditions fetched successfully', ThresholdConditionSerializer(many=True)),
            404: 'Threshold condition not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, pk=None):
        try:
            if pk:
                try:
                    condition = ThresholdCondition.objects.get(id=pk)
                    serializer = ThresholdConditionSerializer(condition)
                    return ResponseHelper.success_response(
                        f'Threshold condition with id "{pk}" fetched successfully',
                        serializer.data
                    )
                except ThresholdCondition.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'Threshold condition with id "{pk}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                conditions = ThresholdCondition.objects.all()
                serializer = ThresholdConditionSerializer(conditions, many=True)
                return ResponseHelper.success_response('All threshold conditions fetched successfully', serializer.data)
        except ValidationError as e:
            return ResponseHelper.error_response(f"Invalid input: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in GET method (ThresholdCondition)")
            return ResponseHelper.error_response("An unexpected error occurred.", str(e),
                                                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=ThresholdConditionSerializer,
        responses={
            201: openapi.Response('Threshold condition created successfully', ThresholdConditionSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            serializer = ThresholdConditionSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Threshold condition created successfully',
                                                       serializer.data,
                                                       status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors,
                                                     status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating ThresholdCondition")
            return ResponseHelper.error_response('Internal server error while creating data', str(e),
                                                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=ThresholdConditionSerializer,
        responses={
            200: openapi.Response('Threshold condition updated successfully', ThresholdConditionSerializer),
            400: 'ID is required in URL to update data or invalid data',
            404: 'Threshold condition not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response('ID is required in URL to update data',
                                                 status_code=status.HTTP_400_BAD_REQUEST)
        try:
            condition = ThresholdCondition.objects.get(id=pk)
        except ThresholdCondition.DoesNotExist:
            return ResponseHelper.error_response(f'Threshold condition with id "{pk}" not found',
                                                 status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = ThresholdConditionSerializer(condition, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Threshold condition updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors,
                                                     status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating ThresholdCondition")
            return ResponseHelper.error_response('Internal server error while updating data', str(e),
                                                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        responses={
            200: 'Threshold condition deleted successfully',
            400: 'ID is required in URL to delete data',
            404: 'Threshold condition not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk=None):
        if not pk:
            return ResponseHelper.error_response('ID is required in URL to delete data',
                                                 status_code=status.HTTP_400_BAD_REQUEST)
        try:
            condition = ThresholdCondition.objects.get(id=pk)
            condition.delete()
            return ResponseHelper.success_response(f'Threshold condition with id "{pk}" deleted successfully')
        except ThresholdCondition.DoesNotExist:
            return ResponseHelper.error_response(f'Threshold condition with id "{pk}" not found',
                                                 status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting ThresholdCondition")
            return ResponseHelper.error_response('Internal server error while deleting data', str(e),
                                                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)