from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from io import BytesIO, StringIO
import re
import csv

from user_app.models import LetterTemplate, GarnishmentOrder, EmployeeDetail, PayeeDetails
from user_app.serializers import LetterTemplateSerializer, LetterTemplateFillSerializer, LetterTemplateVariableValuesSerializer, GarnishmentOrderSerializer, LetterTemplateExportSerializer
from user_app.services.letter_template_data_service import LetterTemplateDataService
from processor.garnishment_library.utils import ResponseHelper
from processor.models.garnishment_result.result import GarnishmentResult
from rest_framework.decorators import api_view

# PDF generation
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        REPORTLAB_AVAILABLE = True
    except ImportError:
        REPORTLAB_AVAILABLE = False

# DOC generation
try:
    from docx import Document
    from docx.shared import Inches
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# HTML to text conversion
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False


class LetterTemplateListAPI(APIView):
    """
    API view to list all letter templates.
    """
    
    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', LetterTemplateSerializer(many=True)),
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Retrieve all letter templates.
        Query params:
        - is_active: Filter by active status (true/false)
        """
        try:
            queryset = LetterTemplate.objects.all()
            
            # Filter by is_active if provided
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true'
                queryset = queryset.filter(is_active=is_active_bool)
            
            serializer = LetterTemplateSerializer(queryset, many=True)
            return ResponseHelper.success_response(
                'Letter templates fetched successfully',
                serializer.data
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch letter templates',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateRetrieveAPI(APIView):
    """
    API view to retrieve a single letter template by ID.
    """
    
    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', LetterTemplateSerializer),
            404: 'Template not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, pk):
        """
        Retrieve a specific letter template by ID.
        """
        try:
            template = LetterTemplate.objects.get(pk=pk)
            serializer = LetterTemplateSerializer(template)
            return ResponseHelper.success_response(
                'Letter template fetched successfully',
                serializer.data
            )
        except LetterTemplate.DoesNotExist:
            return ResponseHelper.error_response(
                f'Letter template with id "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch letter template',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateCreateAPI(APIView):
    """
    API view to create a new letter template.
    """
    
    @swagger_auto_schema(
        request_body=LetterTemplateSerializer,
        responses={
            201: openapi.Response('Created', LetterTemplateSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new letter template.
        """
        try:
            serializer = LetterTemplateSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Letter template created successfully',
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
                'Internal server error while creating letter template',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateUpdateAPI(APIView):
    """
    API view to update an existing letter template.
    """
    
    @swagger_auto_schema(
        request_body=LetterTemplateSerializer,
        responses={
            200: openapi.Response('Updated', LetterTemplateSerializer),
            400: 'Invalid data',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pk):
        """
        Update an existing letter template (full update).
        """
        try:
            template = LetterTemplate.objects.get(pk=pk)
        except LetterTemplate.DoesNotExist:
            return ResponseHelper.error_response(
                f'Letter template with id "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        try:
            serializer = LetterTemplateSerializer(template, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Letter template updated successfully',
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
                'Internal server error while updating letter template',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        request_body=LetterTemplateSerializer,
        responses={
            200: openapi.Response('Updated', LetterTemplateSerializer),
            400: 'Invalid data',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def patch(self, request, pk):
        """
        Partially update an existing letter template.
        """
        try:
            template = LetterTemplate.objects.get(pk=pk)
        except LetterTemplate.DoesNotExist:
            return ResponseHelper.error_response(
                f'Letter template with id "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        try:
            serializer = LetterTemplateSerializer(template, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Letter template updated successfully',
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
                'Internal server error while updating letter template',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateVariablesAPI(APIView):
    """
    API view to fetch available template variables for an employee.
    This endpoint is used by the frontend to show available variables
    that can be dragged and dropped into templates.
    """
    
    @swagger_auto_schema(
        request_body=LetterTemplateVariableValuesSerializer,
        responses={
            200: 'Success - Returns available template variables',
            400: 'Invalid request data',
            404: 'Employee or order not found',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Get available template variables for an employee.
        
        Request Body (JSON):
        {
            "employee_id": "DA0001",  // required
            "order_id": "CSE001"      // optional
        }
        
        Returns:
        {
            "success": true,
            "message": "Template variables fetched successfully",
            "data": {
                "employee_details": {
                    "employee_id": "DA0001",
                    "first_name": "John",
                    "last_name": "Doe",
                    "full_name": "John Doe",
                    ...
                },
                "order_data": {
                    "case_id": "CSE001",
                    "ordered_amount": "500.00",
                    "withholding_amount": "450.00",
                    ...
                },
                "sdu_data": {
                    "sdu_payee": "State Disbursement Unit",
                    "sdu_address": "123 Main St",
                    ...
                }
            }
        }
        """
        try:
            serializer = LetterTemplateVariableValuesSerializer(data=request.data)
            if not serializer.is_valid():
                return ResponseHelper.error_response(
                    'Invalid request data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            employee_id = serializer.validated_data['employee_id']
            order_id = serializer.validated_data.get('order_id')
            
            # Clean up order_id if it's empty string
            if order_id == '':
                order_id = None
            
            # Fetch all data
            try:
                employee_data = LetterTemplateDataService.fetch_employee_data(employee_id)
                order_data = LetterTemplateDataService.fetch_order_data(employee_id, order_id)
                sdu_data = LetterTemplateDataService.fetch_sdu_data(employee_id, order_id)
            except ValueError as e:
                return ResponseHelper.error_response(
                    str(e),
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Structure the response with simple key-value pairs
            response_data = {
                "employee_details": employee_data
            }
            
            # Add order data if available
            if order_data:
                response_data["order_data"] = order_data
            else:
                response_data["order_data"] = {}
            
            # Add SDU data if available
            if sdu_data:
                response_data["sdu_data"] = sdu_data
            else:
                response_data["sdu_data"] = {}
            
            return ResponseHelper.success_response(
                'Template variables fetched successfully',
                response_data
            )
            
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch template variables',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

#get available variables for drag and drop
class LetterTemplateAvailableVariablesAPI(APIView):
    """
    API view to fetch available template variable names (without data).
    This endpoint is used by the frontend to show available variables
    that can be dragged and dropped when creating templates.
    No employee_id or order_id required - just returns the list of available variables.
    """
    
    @swagger_auto_schema(
        responses={
            200: 'Success - Returns available template variable names organized by category',
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Get available template variable names organized by category.
        This endpoint returns only the variable names and descriptions,
        not actual data values. Used for drag-and-drop in template editor.
        
        Returns:
        {
            "success": true,
            "message": "Available template variables fetched successfully",
            "data": {
                "employee_details": {
                    "employee_id": "Employee ID (ee_id)",
                    "first_name": "First Name",
                    "last_name": "Last Name",
                    ...
                },
                "order_data": {
                    "case_id": "Case ID",
                    "ordered_amount": "Ordered Amount",
                    "withholding_amount": "Withholding Amount",
                    ...
                },
                "sdu_data": {
                    "sdu_payee": "SDU Payee",
                    "sdu_address": "SDU Address",
                    ...
                }
            }
        }
        """
        try:
            available_variables = LetterTemplateDataService.get_available_variables()
            
            return ResponseHelper.success_response(
                'Available template variables fetched successfully',
                available_variables
            )
            
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch available template variables',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateDeleteAPI(APIView):
    """
    API view to delete a letter template.
    """
    
    @swagger_auto_schema(
        responses={
            200: 'Deleted successfully',
            404: 'Not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk):
        """
        Delete a letter template by ID.
        """
        try:
            template = LetterTemplate.objects.get(pk=pk)
            template.delete()
            return ResponseHelper.success_response(
                f'Letter template with id "{pk}" deleted successfully'
            )
        except LetterTemplate.DoesNotExist:
            return ResponseHelper.error_response(
                f'Letter template with id "{pk}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHelper.error_response(
                'Internal server error while deleting letter template',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateFillAPI(APIView):
    """
    API view to fill template variables and export in different formats (PDF, DOC, TXT).
    """
    
    @swagger_auto_schema(
        request_body=LetterTemplateFillSerializer,
        responses={
            200: 'File generated successfully',
            400: 'Invalid data',
            404: 'Template not found',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Fill template variables and export in specified format.
        
        Two modes supported:
        1. Automatic mode (recommended):
        {
            "template_id": 1,
            "employee_id": "EMP001",  // or employee primary key
            "order_id": "CASE001",     // optional: order case_id or primary key
            "format": "pdf"            // optional: pdf, doc, docx, or txt (default: pdf)
        }
        
        2. Manual mode (backward compatible):
        {
            "template_id": 1,
            "variable_values": {
                "name": "John Doe",
                "date": "2024-01-01",
                ...
            },
            "format": "pdf"
        }
        
        If both employee_id and variable_values are provided, variable_values will override
        the auto-fetched values for those specific keys.
        """
        try:
            serializer = LetterTemplateFillSerializer(data=request.data)
            if not serializer.is_valid():
                return ResponseHelper.error_response(
                    'Invalid data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            template_id = serializer.validated_data['template_id']
            employee_id = serializer.validated_data.get('employee_id')
            order_id = serializer.validated_data.get('order_id')
            # Handle None or empty dict for variable_values
            manual_variable_values = serializer.validated_data.get('variable_values') or {}
            export_format = serializer.validated_data.get('format', 'pdf').lower()
            
            # Clean up employee_id if it's empty string
            if employee_id == '':
                employee_id = None
            
            try:
                template = LetterTemplate.objects.get(pk=template_id)
            except LetterTemplate.DoesNotExist:
                return ResponseHelper.error_response(
                    f'Letter template with id "{template_id}" not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Determine variable values
            if employee_id:
                # Automatic mode: Fetch data from database
                try:
                    # Fetch all template variables from employee, order, and SDU data
                    auto_variable_values = LetterTemplateDataService.get_all_template_variables(
                        employee_id=employee_id,
                        order_id=order_id
                    )
                    
                    # Merge with manual variable_values (manual values override auto-fetched)
                    variable_values = {**auto_variable_values, **manual_variable_values}
                    
                except ValueError as e:
                    # Employee or order not found
                    return ResponseHelper.error_response(
                        str(e),
                        status_code=status.HTTP_404_NOT_FOUND
                    )
                except Exception as e:
                    return ResponseHelper.error_response(
                        f'Failed to fetch employee/order data: {str(e)}',
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # Manual mode: Use provided variable_values
                variable_values = manual_variable_values
            
            # Fill template variables
            filled_content = self._fill_template(template.html_content, variable_values)
            
            # Generate file based on format
            if export_format == 'pdf':
                return self._generate_pdf(filled_content, template.name)
            elif export_format in ['doc', 'docx']:
                return self._generate_docx(filled_content, template.name)
            elif export_format in ['txt', 'text']:
                return self._generate_txt(filled_content, template.name)
            else:
                return ResponseHelper.error_response(
                    f'Unsupported format: {export_format}. Supported formats: pdf, doc, docx, txt, text',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to generate letter',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _fill_template(self, html_content, variable_values):
        """
        Replace {{variable_name}} placeholders with actual values.
        """
        filled_content = html_content
        for var_name, var_value in variable_values.items():
            # Replace {{variable_name}} with actual value
            pattern = r'\{\{' + re.escape(var_name) + r'\}\}'
            filled_content = re.sub(pattern, str(var_value), filled_content)
        return filled_content
    
    def _generate_pdf(self, html_content, template_name):
        """
        Generate PDF from HTML content.
        """
        if WEASYPRINT_AVAILABLE:
            # Use WeasyPrint for better HTML to PDF conversion
            html = HTML(string=html_content)
            pdf_buffer = BytesIO()
            html.write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
            response = HttpResponse(pdf_buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{template_name}_letter.pdf"'
            return response
        elif REPORTLAB_AVAILABLE:
            # Fallback to ReportLab
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Convert HTML to plain text for ReportLab
            text_content = self._html_to_text(html_content)
            paragraphs = text_content.split('\n\n')
            
            for para in paragraphs:
                if para.strip():
                    p = Paragraph(para.strip(), styles['Normal'])
                    story.append(p)
                    story.append(Spacer(1, 0.2*inch))
            
            doc.build(story)
            pdf_buffer.seek(0)
            
            response = HttpResponse(pdf_buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{template_name}_letter.pdf"'
            return response
        else:
            return ResponseHelper.error_response(
                'PDF generation not available. Please install weasyprint or reportlab.',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    def _generate_docx(self, html_content, template_name):
        """
        Generate DOCX from HTML content.
        """
        if DOCX_AVAILABLE:
            doc = Document()
            
            # Convert HTML to text and add to document
            if HTML2TEXT_AVAILABLE:
                text_content = html2text.html2text(html_content)
            else:
                text_content = self._html_to_text(html_content)
            
            paragraphs = text_content.split('\n\n')
            
            for para in paragraphs:
                if para.strip():
                    doc.add_paragraph(para.strip())
            
            doc_buffer = BytesIO()
            doc.save(doc_buffer)
            doc_buffer.seek(0)
            
            response = HttpResponse(
                doc_buffer,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{template_name}_letter.docx"'
            return response
        else:
            return ResponseHelper.error_response(
                'DOCX generation not available. Please install python-docx.',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    def _generate_txt(self, html_content, template_name):
        """
        Generate TXT from HTML content.
        """
        text_content = self._html_to_text(html_content)
        
        response = HttpResponse(text_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{template_name}_letter.txt"'
        return response
    
    def _html_to_text(self, html_content):
        """
        Basic HTML to text conversion.
        """
        if HTML2TEXT_AVAILABLE:
            return html2text.html2text(html_content)
        else:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()


class LetterTemplateOrderFilterAPI(APIView):
    """
    API view to filter orders by employee_id for letter management.
    This endpoint returns all orders associated with a specific employee.
    """
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'employee_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Employee ID (ee_id) or primary key',
                    required=['employee_id']
                )
            },
            required=['employee_id']
        ),
        responses={
            200: 'Success - Returns filtered orders',
            400: 'Invalid request data',
            404: 'Employee not found',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Filter orders by employee_id for letter management.
        
        Request Body (JSON):
        {
            "employee_id": "DA0001"  // required: Employee ID (ee_id) or primary key
        }
        
        Returns:
        {
            "success": true,
            "message": "Orders fetched successfully",
            "data": [
                {
                    "id": 1,
                    "case_id": "CSE001",
                    "ssn": "...",
                    "issuing_state": "California",
                    "garnishment_type": "Child Support",
                    "ordered_amount": "500.00",
                    "withholding_amount": "450.00",
                    ...
                },
                ...
            ]
        }
        """
        try:
            employee_id = request.data.get('employee_id')
            
            if not employee_id:
                return ResponseHelper.error_response(
                    'employee_id is required in request body',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get employee by ee_id or primary key
            try:
                if isinstance(employee_id, str):
                    employee = EmployeeDetail.objects.get(ee_id=employee_id)
                else:
                    employee = EmployeeDetail.objects.get(pk=employee_id)
            except EmployeeDetail.DoesNotExist:
                return ResponseHelper.error_response(
                    f'Employee with id "{employee_id}" not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Fetch all orders for this employee
            orders = GarnishmentOrder.objects.filter(
                employee=employee
            ).select_related(
                'employee', 'issuing_state', 'garnishment_type'
            ).order_by('-created_at')
            
            # Serialize the orders
            serializer = GarnishmentOrderSerializer(orders, many=True)
            
            return ResponseHelper.success_response(
                f'Orders fetched successfully for employee {employee_id}',
                serializer.data
            )
            
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to fetch orders',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LetterTemplateExportCSVAPI(APIView):
    """
    API view to export employee details, order, payee, and GarnishmentResult data to CSV or TXT.
    Only exports data for employees who have records in GarnishmentResult.
    """
    
    @swagger_auto_schema(
        request_body=LetterTemplateExportSerializer,
        responses={
            200: 'File generated successfully',
            400: 'Invalid format or request data',
            404: 'No data found',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Export employee details, order, payee, and GarnishmentResult withholding_amount to CSV or TXT.
        Only exports data for employees present in GarnishmentResult.
        
        Request Body (JSON):
        {
            "format": "csv"  // optional: csv or txt (default: csv)
        }
        
        Returns:
        CSV or TXT file with columns:
        - Employee Details: ee_id, first_name, last_name, ssn, home_state, work_state, etc.
        - Order Details: case_id, ordered_amount, withholding_amount (from order), issued_date, etc.
        - Payee Details: payee, payee_type, routing_number, bank_account, etc.
        - GarnishmentResult: withholding_amount (from GarnishmentResult)
        """
        try:
            # Validate request data
            serializer = LetterTemplateExportSerializer(data=request.data)
            if not serializer.is_valid():
                return ResponseHelper.error_response(
                    'Invalid request data',
                    serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get export format from request body
            export_format = serializer.validated_data.get('format', 'csv').lower()
            
            # Get all GarnishmentResult records with related data
            results = GarnishmentResult.objects.select_related(
                'ee',  # EmployeeDetail
                'case',  # GarnishmentOrder
                'case__issuing_state',  # State
                'case__garnishment_type',  # GarnishmentType
                'ee__home_state',  # State
                'ee__work_state',  # State
                'ee__client',  # Client
                'ee__filing_status',  # FedFilingStatus
            ).all()
            
            if not results.exists():
                return ResponseHelper.error_response(
                    'No garnishment results found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Define header columns (without Batch ID and Processed At)
            header = [
                # Employee Details
                'Employee ID (ee_id)',
                'First Name',
                'Middle Name',
                'Last Name',
                'SSN',
                'Home State',
                'Work State',
                'Gender',
                'Marital Status',
                'Number of Exemptions',
                'Number of Dependent Children',
                'Filing Status',
                'Client ID',
                'Client Name',
                
                # Order Details
                'Case ID',
                'Ordered Amount',
                'Withholding Amount (Order)',
                'Garnishment Type',
                'Issued Date',
                'Received Date',
                'Start Date',
                'Stop Date',
                'Deduction Code',
                'FEIN',
                'Garnishing Authority',
                'FIPS Code',
                'Payee (Order)',
                'Is Consumer Debt',
                
                # Payee Details
                'Payee (PayeeDetails)',
                'Payee Type',
                'Routing Number',
                'Bank Account',
                'Case Number Required',
                'Case Number Format',
                'FIPS Required',
                'FIPS Length',
                
                # GarnishmentResult
                'Withholding Amount (Result)',
            ]
            
            if export_format == 'csv':
                return self._generate_csv(results, header)
            else:  # txt
                return self._generate_txt(results, header)
                
        except Exception as e:
            return ResponseHelper.error_response(
                'Failed to export data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_csv(self, results, header):
        """Generate CSV file from results."""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write CSV header
        writer.writerow(header)
        
        # Write data rows
        for result in results:
            employee = result.ee
            order = result.case
            
            # Get payee details (try PayeeDetails first, fallback to order.payee)
            payee_details = PayeeDetails.objects.filter(
                case_id=order,
                is_active=True
            ).first()
            
            # Employee Details
            row = [
                employee.ee_id or '',
                employee.first_name or '',
                employee.middle_name or '',
                employee.last_name or '',
                employee.ssn or '',
                employee.home_state.state if employee.home_state else '',
                employee.work_state.state if employee.work_state else '',
                employee.gender or '',
                employee.marital_status or '',
                employee.number_of_exemptions or 0,
                employee.number_of_dependent_child or 0,
                employee.filing_status.name if employee.filing_status else '',
                employee.client.client_id if employee.client else '',
                employee.client.legal_name if employee.client else '',
                
                # Order Details
                order.case_id or '',
                str(order.ordered_amount) if order.ordered_amount else '0.00',
                str(order.withholding_amount) if order.withholding_amount else '0.00',
                order.garnishment_type.type if order.garnishment_type else '',
                order.issued_date.strftime('%Y-%m-%d') if order.issued_date else '',
                order.received_date.strftime('%Y-%m-%d') if order.received_date else '',
                order.start_date.strftime('%Y-%m-%d') if order.start_date else '',
                order.stop_date.strftime('%Y-%m-%d') if order.stop_date else '',
                order.deduction_code or '',
                order.fein or '',
                order.garnishing_authority or '',
                order.fips_code or '',
                order.payee or '',
                'Yes' if order.is_consumer_debt else 'No',
                
                # Payee Details
                payee_details.payee if payee_details else '',
                payee_details.payee_type if payee_details else '',
                payee_details.routing_number if payee_details else '',
                payee_details.bank_account if payee_details else '',
                'Yes' if payee_details and payee_details.case_number_required else 'No',
                payee_details.case_number_format if payee_details else '',
                'Yes' if payee_details and payee_details.fips_required else 'No',
                payee_details.fips_length if payee_details else '',
                
                # GarnishmentResult
                str(result.withholding_amount) if result.withholding_amount else '0.00',
            ]
            writer.writerow(row)
        
        # Prepare HTTP response with CSV
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="garnishment_export.csv"'
        return response
    
    def _generate_txt(self, results, header):
        """Generate TXT file from results."""
        output = StringIO()
        
        # Write header row
        output.write('\t'.join(header))
        output.write('\n')
        
        # Write data rows
        for result in results:
            employee = result.ee
            order = result.case
            
            # Get payee details (try PayeeDetails first, fallback to order.payee)
            payee_details = PayeeDetails.objects.filter(
                case_id=order,
                is_active=True
            ).first()
            
            # Employee Details
            row = [
                employee.ee_id or '',
                employee.first_name or '',
                employee.middle_name or '',
                employee.last_name or '',
                employee.ssn or '',
                employee.home_state.state if employee.home_state else '',
                employee.work_state.state if employee.work_state else '',
                employee.gender or '',
                employee.marital_status or '',
                str(employee.number_of_exemptions) if employee.number_of_exemptions else '0',
                str(employee.number_of_dependent_child) if employee.number_of_dependent_child else '0',
                employee.filing_status.name if employee.filing_status else '',
                employee.client.client_id if employee.client else '',
                employee.client.legal_name if employee.client else '',
                
                # Order Details
                order.case_id or '',
                str(order.ordered_amount) if order.ordered_amount else '0.00',
                str(order.withholding_amount) if order.withholding_amount else '0.00',
                order.garnishment_type.type if order.garnishment_type else '',
                order.issued_date.strftime('%Y-%m-%d') if order.issued_date else '',
                order.received_date.strftime('%Y-%m-%d') if order.received_date else '',
                order.start_date.strftime('%Y-%m-%d') if order.start_date else '',
                order.stop_date.strftime('%Y-%m-%d') if order.stop_date else '',
                order.deduction_code or '',
                order.fein or '',
                order.garnishing_authority or '',
                order.fips_code or '',
                order.payee or '',
                'Yes' if order.is_consumer_debt else 'No',
                
                # Payee Details
                payee_details.payee if payee_details else '',
                payee_details.payee_type if payee_details else '',
                payee_details.routing_number if payee_details else '',
                payee_details.bank_account if payee_details else '',
                'Yes' if payee_details and payee_details.case_number_required else 'No',
                payee_details.case_number_format if payee_details else '',
                'Yes' if payee_details and payee_details.fips_required else 'No',
                str(payee_details.fips_length) if payee_details and payee_details.fips_length else '',
                
                # GarnishmentResult
                str(result.withholding_amount) if result.withholding_amount else '0.00',
            ]
            output.write('\t'.join(row))
            output.write('\n')
        
        # Prepare HTTP response with TXT
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="garnishment_export.txt"'
        return response

