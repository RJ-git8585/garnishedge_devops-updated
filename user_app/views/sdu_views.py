from user_app.models import SDU
from processor.models.shared_model.state import State
from processor.garnishment_library.utils.response import ResponseHelper
import logging
from django.core.exceptions import ValidationError
from user_app.serializers import SDUSerializer
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from io import BytesIO
from rest_framework.permissions import AllowAny
from datetime import datetime
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import pandas as pd
import csv

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


class SDUImportView(APIView):
    """
    API view to handle the import (upsert) of SDUs from a file.
    Updates existing SDUs by combination of case_id and state, or creates new ones.
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
            
            added_sdus = []
            updated_sdus = []
            
            for _, row in df.iterrows():
                try:
                    sdu_data = {
                        "payee": row.get("payee"),
                        "state": row.get("state"),
                        "case_id": row.get("case_id"),
                        "address": row.get("address"),
                        "contact": row.get("contact"),
                        "fips_code": row.get("fips_code"),
                        "is_active": row.get("is_active", True),
                    }
                    
                    # Check if case_id and state exist (required for unique identification)
                    case_id = sdu_data.get("case_id")
                    state = sdu_data.get("state")
                    fips_code = sdu_data.get("fips_code")
                    
                    if not case_id or not fips_code:
                        # Skip rows without required identifiers
                        continue
                    
                    # Try to find existing SDU by case_id and fips_code
                    existing_sdu = SDU.objects.filter(
                        case_id__case_id=case_id,
                        fips_code=fips_code
                    ).first()
                    
                    sdu_identifier = f"{case_id}_{fips_code}"
                    
                    if existing_sdu:
                        # Update existing SDU
                        serializer = SDUSerializer(
                            existing_sdu, 
                            data=sdu_data, 
                            partial=True
                        )
                        if serializer.is_valid():
                            serializer.save()
                            updated_sdus.append(sdu_identifier)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for SDU {sdu_identifier}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new SDU
                        serializer = SDUSerializer(data=sdu_data)
                        if serializer.is_valid():
                            serializer.save()
                            added_sdus.append(sdu_identifier)
                        else:
                            return ResponseHelper.error_response(
                                message=f"Validation error for SDU {sdu_identifier}",
                                error=serializer.errors,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                            
                except Exception as row_e:
                    logger.exception(f"Error processing SDU row: {str(row_e)}")
                    return ResponseHelper.error_response(
                        message="Error processing row",
                        error=str(row_e),
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Build response data
            response_data = {}
            
            if added_sdus:
                response_data["added_sdus"] = added_sdus
                response_data["added_count"] = len(added_sdus)
            
            if updated_sdus:
                response_data["updated_sdus"] = updated_sdus
                response_data["updated_count"] = len(updated_sdus)
            
            if not added_sdus and not updated_sdus:
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
            logger.exception(f"Error importing SDUs: {str(e)}")
            return ResponseHelper.error_response(
                message="Failed to import SDUs",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportSDUDataView(APIView):
    """
    API view to export SDU data as an Excel file.
    Provides robust exception handling and clear response messages.
    """
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        responses={
            200: 'Excel file exported successfully',
            404: 'No SDUs found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Handles GET request to export all SDUs to an Excel file.
        """
        try:
            # Fetch all SDUs from the database
            sdus = SDU.objects.all()
            if not sdus.exists():
                return ResponseHelper.error_response(
                    message="No SDUs found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = SDUSerializer(sdus, many=True)

            # Create Excel workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "SDUs"

            # Define header fields
            header_fields = [
                "id", "payee", "state", "case_id", "address", 
                "contact", "fips_code", "is_active"
            ]

            ws.append(header_fields)

            # Write data rows to the worksheet
            for sdu in serializer.data:
                row = [sdu.get(field, '') for field in header_fields]
                ws.append(row)

            # Save workbook to in-memory buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # Prepare HTTP response with Excel content
            filename = f'sdus_{datetime.today().strftime("%m-%d-%y")}.xlsx'
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.exception(f"Error exporting SDU data: {str(e)}")
            return ResponseHelper.error_response(
                message="Failed to export SDU data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )