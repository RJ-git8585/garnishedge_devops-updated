from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime
from rest_framework.permissions import AllowAny
import pandas as pd
import csv

from user_app.models import Client
from user_app.serializers import ClientSerializer
from processor.garnishment_library import ResponseHelper


class ClientDetailsAPI(APIView):
    """
    API view for CRUD operations on Client details.
    Provides robust exception handling and clear response messages.
    """
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


class ClientImportView(APIView):
    """
    API view to handle the import (upsert) of clients from a file.
    Updates existing clients by client_id or creates new ones.
    """
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Excel or CSV file to upload"
            ),
        ],
        responses={
            201: 'File processed successfully',
            400: 'No file provided or unsupported file format',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            if 'file' not in request.FILES:
                return ResponseHelper.error_response(
                    message="No file provided",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES['file']
            file_name = file.name

            # Read file based on extension
            if file_name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file_name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb', '.odf', '.ods', '.odt')):
                df = pd.read_excel(file)
            else:
                return ResponseHelper.error_response(
                    message="Unsupported file format. Please upload a CSV or Excel file.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            added_clients = []
            updated_clients = []
            
            for _, row in df.iterrows():
                try:
                    client_data = {
                        "client_id": row.get("client_id"),
                        "peo": row.get("peo"),
                        "state": row.get("state"),
                        "legal_name": row.get("legal_name"),
                        "dba": row.get("dba"),
                        "service_type": row.get("service_type"),
                        "is_active": row.get("is_active", True),
                    }
                    
                    # Check if client_id exists
                    client_id = client_data.get("client_id")
                    if not client_id:
                        # Skip rows without client_id
                        continue
                    
                    # Try to find existing client by client_id
                    existing_client = Client.objects.filter(client_id=client_id).first()
                    
                    if existing_client:
                        # Update existing client
                        serializer = ClientSerializer(
                            existing_client, 
                            data=client_data, 
                            partial=True
                        )
                        if serializer.is_valid():
                            serializer.save()
                            updated_clients.append(client_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for client_id {client_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new client
                        serializer = ClientSerializer(data=client_data)
                        if serializer.is_valid():
                            serializer.save()
                            added_clients.append(client_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for client_id {client_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                            
                except Exception as row_e:
                    return ResponseHelper.error_response(
                        message="Error processing row",
                        error=str(row_e),
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Build response data
            response_data = {}
            
            if added_clients:
                response_data["added_clients"] = added_clients
                response_data["added_count"] = len(added_clients)
            
            if updated_clients:
                response_data["updated_clients"] = updated_clients
                response_data["updated_count"] = len(updated_clients)
            
            if not added_clients and not updated_clients:
                return ResponseHelper.success_response(
                    message="No valid data to process",
                    data=response_data,
                    status_code=status.HTTP_200_OK
                )

            return ResponseHelper.success_response(
                message="File processed successfully",
                data=response_data,
                status_code=status.HTTP_201_CREATED
            )

        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to import clients",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportClientDataView(APIView):
    """
    API view to export client data as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    
    @swagger_auto_schema(
        responses={
            200: 'Excel file exported successfully',
            404: 'No clients found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Handles GET request to export all clients to an Excel file.
        """
        try:
            # Fetch all clients from the database
            clients = Client.objects.all()
            if not clients.exists():
                return ResponseHelper.error_response(
                    message="No clients found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = ClientSerializer(clients, many=True)

            # Create Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Clients"

            # Define header fields
            header_fields = [
                "id", "client_id", "peo", "state", "legal_name", 
                "dba", "service_type", "is_active", "created_at", "updated_at"
            ]

            ws.append(header_fields)

            # Write data rows to the worksheet
            for client in serializer.data:
                row = [client.get(field, '') for field in header_fields]
                ws.append(row)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'clients_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to export client data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
