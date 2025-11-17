from processor.models import GarnishmentType
from processor.garnishment_library.utils.response import ResponseHelper
from processor.serializers import GarnishmentTypeSerializer, GarnishmentTypeCodeSerializer
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class GarnishmentTypeAPIView(APIView):
    """
    API view for CRUD operations on GarnishmentType.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('GarnishmentType data fetched successfully', GarnishmentTypeSerializer(many=True)),
            404: 'GarnishmentType not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, pk=None):
        """
        Retrieve GarnishmentType records.
        - GET /garnishment_type/details/ - Get all records
        - GET /garnishment_type/details/<pk>/ - Get specific record by primary key
        """
        try:
            if pk:
                try:
                    garnishment_type = GarnishmentType.objects.get(pk=pk)
                    serializer = GarnishmentTypeSerializer(garnishment_type)
                    return ResponseHelper.success_response(
                        f'GarnishmentType with id "{pk}" fetched successfully',
                        serializer.data,
                        status_code=status.HTTP_200_OK
                    )
                except GarnishmentType.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'GarnishmentType with id "{pk}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                garnishment_types = GarnishmentType.objects.all().order_by('type')
                serializer = GarnishmentTypeSerializer(garnishment_types, many=True)
                return ResponseHelper.success_response(
                    'All GarnishmentType data fetched successfully',
                    serializer.data,
                    status_code=status.HTTP_200_OK
                )
        except Exception as e:
            logger.exception("Unexpected error in GET method of GarnishmentTypeAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch GarnishmentType data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentTypeSerializer,
        responses={
            201: openapi.Response('GarnishmentType created successfully', GarnishmentTypeSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new GarnishmentType record.
        """
        try:
            serializer = GarnishmentTypeSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'GarnishmentType created successfully',
                    serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Unexpected error in POST method of GarnishmentTypeAPIView")
            return ResponseHelper.error_response(
                'Failed to create GarnishmentType',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentTypeSerializer,
        responses={
            200: openapi.Response('GarnishmentType updated successfully', GarnishmentTypeSerializer),
            400: 'Invalid data or pk is required',
            404: 'GarnishmentType not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pk=None):
        """
        Update a GarnishmentType record.
        PUT /garnishment_type/details/<pk>/ - Update specific record
        """
        if not pk:
            return ResponseHelper.error_response(
                'Primary key (pk) is required in URL to update data',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            try:
                garnishment_type = GarnishmentType.objects.get(pk=pk)
            except GarnishmentType.DoesNotExist:
                return ResponseHelper.error_response(
                    f'GarnishmentType with id "{pk}" not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = GarnishmentTypeSerializer(garnishment_type, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'GarnishmentType updated successfully',
                    serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Unexpected error in PUT method of GarnishmentTypeAPIView")
            return ResponseHelper.error_response(
                'Failed to update GarnishmentType',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'GarnishmentType deleted successfully',
            400: 'Primary key (pk) is required in URL',
            404: 'GarnishmentType not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk=None):
        """
        Delete a GarnishmentType record.
        DELETE /garnishment_type/details/<pk>/ - Delete specific record
        """
        if not pk:
            return ResponseHelper.error_response(
                'Primary key (pk) is required in URL to delete data',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            try:
                garnishment_type = GarnishmentType.objects.get(pk=pk)
            except GarnishmentType.DoesNotExist:
                return ResponseHelper.error_response(
                    f'GarnishmentType with id "{pk}" not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )

            garnishment_type.delete()
            return ResponseHelper.success_response(
                f'GarnishmentType with id "{pk}" deleted successfully',
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Unexpected error in DELETE method of GarnishmentTypeAPIView")
            return ResponseHelper.error_response(
                'Failed to delete GarnishmentType',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GarnishmentTypeCodeAPIView(APIView):
    """
    API view for fetching code and type fields from GarnishmentType table.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('GarnishmentType codes fetched successfully', GarnishmentTypeCodeSerializer(many=True)),
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Retrieve all GarnishmentType codes and types.
        GET /garnishment_type/codes/ - Get all codes and types
        """
        try:
            garnishment_types = GarnishmentType.objects.all().order_by('code')
            serializer = GarnishmentTypeCodeSerializer(garnishment_types, many=True)
            return ResponseHelper.success_response(
                'GarnishmentType codes fetched successfully',
                serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Unexpected error in GET method of GarnishmentTypeCodeAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch GarnishmentType codes',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

