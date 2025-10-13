from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime
import pandas as pd
import csv
from rest_framework.permissions import AllowAny

from user_app.models import PEO
from user_app.serializers import PEOSerializer
from processor.garnishment_library.utils import PaginationHelper ,ResponseHelper  


class PEOAPI(APIView):
    """
    API view for listing and creating PEOs.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", PEOSerializer(many=True)),
            500: "Internal Server Error",
        }
    )
    def get(self, request):
        """
        Get paginated list of active PEOs with optional filters:
        - ?state_code=CA
        - ?peo_id=PEO123
        """
        try:
            queryset = PEO.objects.filter(is_active=True).order_by("-created_at")

            state_code = request.query_params.get("state_code")
            peo_id = request.query_params.get("peo_id")

            if state_code:
                queryset = queryset.filter(state__state_code=state_code)
            if peo_id:
                queryset = queryset.filter(peo_id=peo_id)

            result = PaginationHelper.paginate_queryset(queryset, request, PEOSerializer)
            return ResponseHelper.success_response(
                message="PEOs fetched successfully",
                data=result,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to fetch PEOs",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=PEOSerializer,
        responses={
            201: openapi.Response("Created", PEOSerializer),
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        """
        Create a new PEO.
        """
        serializer = PEOSerializer(data=request.data)
        if serializer.is_valid():
            try:
                peo = serializer.save()
                return ResponseHelper.success_response(
                    message="PEO created successfully",
                    data=PEOSerializer(peo).data,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to create PEO",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while creating PEO",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PEOByIdAPI(APIView):
    """
    API view for retrieving, updating, or deleting a specific PEO by ID.
    """

    def get_object(self, pk):
        try:
            return PEO.objects.get(pk=pk, is_active=True)
        except PEO.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", PEOSerializer),
            404: "Not Found",
        }
    )
    def get(self, request, pk):
        """
        Retrieve details of a specific PEO.
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        return ResponseHelper.success_response(
            message="PEO fetched successfully",
            data=PEOSerializer(peo).data,
            status_code=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        request_body=PEOSerializer,
        responses={
            200: openapi.Response("Updated", PEOSerializer),
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, pk):
        """
        Update an existing PEO (partial updates supported).
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = PEOSerializer(peo, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                peo = serializer.save()
                return ResponseHelper.success_response(
                    message="PEO updated successfully",
                    data=PEOSerializer(peo).data,
                    status_code=status.HTTP_200_OK
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to update PEO",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while updating PEO",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    @swagger_auto_schema(
        responses={
            204: "Deleted",
            404: "Not Found",
            500: "Internal Server Error",
        }
    )
    def delete(self, request, pk):
        """
        Soft delete a PEO (mark as inactive).
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            peo.is_active = False
            peo.save(update_fields=["is_active"])
            return ResponseHelper.success_response(
                message="PEO deleted successfully",
                data={},
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to delete PEO",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PEOImportView(APIView):
    """
    API view to handle the import (upsert) of PEOs from a file.
    Updates existing PEOs by peo_id or creates new ones.
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
            
            added_peos = []
            updated_peos = []
            
            for _, row in df.iterrows():
                try:
                    peo_data = {
                        "peo_id": row.get("peo_id"),
                        "state_code": row.get("state_code") or row.get("state"),
                        "name": row.get("name"),
                        "contact_person": row.get("contact_person"),
                        "tax_id": row.get("tax_id"),
                        "is_active": row.get("is_active", True),
                    }
                    
                    # Check if peo_id exists
                    peo_id = peo_data.get("peo_id")
                    if not peo_id:
                        # Skip rows without peo_id
                        continue
                    
                    # Try to find existing PEO by peo_id
                    existing_peo = PEO.objects.filter(peo_id=peo_id).first()
                    
                    if existing_peo:
                        # Update existing PEO
                        serializer = PEOSerializer(
                            existing_peo, 
                            data=peo_data, 
                            partial=True
                        )
                        if serializer.is_valid():
                            serializer.save()
                            updated_peos.append(peo_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for peo_id {peo_id}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new PEO
                        serializer = PEOSerializer(data=peo_data)
                        if serializer.is_valid():
                            serializer.save()
                            added_peos.append(peo_id)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for peo_id {peo_id}",
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
            
            if added_peos:
                response_data["added_peos"] = added_peos
                response_data["added_count"] = len(added_peos)
            
            if updated_peos:
                response_data["updated_peos"] = updated_peos
                response_data["updated_count"] = len(updated_peos)
            
            if not added_peos and not updated_peos:
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
                message="Failed to import PEOs",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportPEODataView(APIView):
    """
    API view to export PEO data as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    
    @swagger_auto_schema(
        responses={
            200: 'Excel file exported successfully',
            404: 'No PEOs found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Handles GET request to export all PEOs to an Excel file.
        """
        try:
            # Fetch all PEOs from the database
            peos = PEO.objects.all()
            if not peos.exists():
                return ResponseHelper.error_response(
                    message="No PEOs found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = PEOSerializer(peos, many=True)

            # Create Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "PEOs"

            # Define header fields
            header_fields = [
                "id", "peo_id", "state", "name", "contact_person", 
                "tax_id", "is_active", "created_at", "updated_at"
            ]

            ws.append(header_fields)

            # Write data rows to the worksheet
            for peo in serializer.data:
                row = [peo.get(field, '') for field in header_fields]
                ws.append(row)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'peos_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to export PEO data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
