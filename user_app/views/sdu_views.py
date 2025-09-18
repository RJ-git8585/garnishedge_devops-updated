from user_app.models import SDU
from processor.models.shared_model.state import State
from processor.garnishment_library.utils.response import ResponseHelper
import logging
from django.core.exceptions import ValidationError
from user_app.serializers import SDUSerializer
from rest_framework.views import APIView
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

logger = logging.getLogger(__name__)

# CRUD operations on SDU using id
class SDUByIDAPIView(APIView):
    """
    API view for CRUD operations on SDU using id.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('SDU fetched successfully', SDUSerializer),
            404: 'SDU not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, id=None):
        """
        Retrieve SDU data by id or all SDUs if not provided.
        """
        try:
            if id:
                try:
                    sdu = SDU.objects.get(id=id)
                    serializer = SDUSerializer(sdu)
                    return ResponseHelper.success_response(
                        f'SDU with id "{id}" fetched successfully', serializer.data
                    )
                except SDU.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'SDU with id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                sdus = SDU.objects.all()
                serializer = SDUSerializer(sdus, many=True)
                return ResponseHelper.success_response('All SDUs fetched successfully', serializer.data)
        except Exception as e:
            logger.exception("Unexpected error in GET method of SDUByIDAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch SDU data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, id=None):
        """
        Create a new SDU.
        """
        try:
            serializer = SDUSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'SDU created successfully', serializer.data, status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Unexpected error in POST method of SDUByIDAPIView")
            return ResponseHelper.error_response(
                'Internal server error while creating SDU', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=SDUSerializer,
        responses={
            200: openapi.Response('SDU updated successfully', SDUSerializer),
            400: 'id is required in URL or invalid data',
            404: 'SDU not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, id=None):
        """
        Update SDU data for a specific id.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to update SDU', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            sdu = SDU.objects.get(id=id)
        except SDU.DoesNotExist:
            return ResponseHelper.error_response(f'SDU with id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = SDUSerializer(sdu, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('SDU updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating SDU")
            return ResponseHelper.error_response(
                'Internal server error while updating SDU', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'SDU deleted successfully',
            400: 'id is required in URL to delete SDU',
            404: 'SDU not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, id=None):
        """
        Delete SDU data for a specific id.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to delete SDU', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            sdu = SDU.objects.get(id=id)
            sdu.delete()
            return ResponseHelper.success_response(f'SDU with id "{id}" deleted successfully')
        except SDU.DoesNotExist:
            return ResponseHelper.error_response(f'SDU with id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in DELETE method of SDUByIDAPIView")
            return ResponseHelper.error_response(
                'Internal server error while deleting SDU', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
# Get SDUs by state name or abbreviation
class SDUByStateAPIView(APIView):
    """
    API view to get SDU(s) by state name or abbreviation using only the SDU table.
    """
    @swagger_auto_schema(
        responses={
            200: openapi.Response('SDUs for state fetched successfully', SDUSerializer(many=True)),
            404: 'No SDUs found for state',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, state=None):
        """
        Retrieve SDU(s) for a specific state name or abbreviation using SDU table.
        """
        if not state:
            return ResponseHelper.error_response('State is required in URL to fetch SDUs', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            # Filter SDUs by related State's name or abbreviation (case-insensitive)
            sdus = SDU.objects.filter(
                state__state__iexact=state.strip()
            ) | SDU.objects.filter(
                state__state_code__iexact=state.strip()
            )
            sdus = sdus.distinct()
            if not sdus.exists():
                return ResponseHelper.error_response(f'No SDUs found for state "{state}"', status_code=status.HTTP_404_NOT_FOUND)
            serializer = SDUSerializer(sdus, many=True)
            return ResponseHelper.success_response(
                f'SDUs for state "{state}" fetched successfully', serializer.data
            )
        except Exception as e:
            logger.exception("Unexpected error in GET method of SDUByStateAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch SDU data for state', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )