from rest_framework.views import APIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from user_app.models import Client
from user_app.serializers import ClientSerializer
from processor.garnishment_library import ResponseHelper
from rest_framework.permissions import AllowAny

class ClientDetailsAPI(APIView):
    """
    API view for CRUD operations on Client details.
    Provides robust exception handling and clear response messages.
    """
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', ClientSerializer(many=True)),
            404: 'Client not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, pk=None):
        """
        Retrieve client details by pk or fetch all clients if pk is not provided.
        """
        try:
            if pk:
                try:
                    client = Client.objects.get(pk=pk)
                    serializer = ClientSerializer(client)
                    return ResponseHelper.success_response(
                        f'Client details for pk "{pk}" fetched successfully',
                        serializer.data
                    )
                except Client.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'pk "{pk}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                clients = Client.objects.all()
                serializer = ClientSerializer(clients, many=True)
                return ResponseHelper.success_response(
                    'All clients fetched successfully',
                    serializer.data
                )
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch client data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=ClientSerializer,
        responses={
            201: openapi.Response('Created', ClientSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new client.
        """
        try:
            serializer = ClientSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Client created successfully',
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
            return ResponseHelper.error_response(
                'Internal server error while creating client',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=ClientSerializer,
        responses={
            200: openapi.Response('Updated', ClientSerializer),
            400: 'Invalid data',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pk=None):
        """
        Update an existing client by pk.
        """
        if not pk:
            return ResponseHelper.error_response(
                'pk is required in URL to update client',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            client = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return ResponseHelper.error_response(
                f'pk "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        try:
            serializer = ClientSerializer(client, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Client updated successfully',
                    serializer.data
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while updating client',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'Deleted successfully',
            400: 'pk is required in URL to delete client',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk=None):
        """
        Delete a client by pk.
        """
        if not pk:
            return ResponseHelper.error_response(
                'pk is required in URL to delete client',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            client = Client.objects.get(pk=pk)
            client.delete()
            return ResponseHelper.success_response(
                f'Client with pk "{pk}" deleted successfully'
            )
        except Client.DoesNotExist:
            return ResponseHelper.error_response(
                f'pk "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while deleting client',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
