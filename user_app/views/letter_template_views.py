from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from io import BytesIO
import re

from user_app.models import LetterTemplate
from user_app.serializers import LetterTemplateSerializer, LetterTemplateFillSerializer
from processor.garnishment_library.utils import ResponseHelper

# PDF generation
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
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
        Request body:
        {
            "template_id": 1,
            "variable_values": {
                "name": "John Doe",
                "date": "2024-01-01",
                ...
            },
            "format": "pdf"  // pdf, doc, docx, or txt
        }
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
            variable_values = serializer.validated_data.get('variable_values', {})
            export_format = serializer.validated_data.get('format', 'pdf').lower()
            
            try:
                template = LetterTemplate.objects.get(pk=template_id)
            except LetterTemplate.DoesNotExist:
                return ResponseHelper.error_response(
                    f'Letter template with id "{template_id}" not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Fill template variables
            filled_content = self._fill_template(template.html_content, variable_values)
            
            # Generate file based on format
            if export_format == 'pdf':
                return self._generate_pdf(filled_content, template.name)
            elif export_format in ['doc', 'docx']:
                return self._generate_docx(filled_content, template.name)
            elif export_format == 'txt':
                return self._generate_txt(filled_content, template.name)
            else:
                return ResponseHelper.error_response(
                    f'Unsupported format: {export_format}. Supported formats: pdf, doc, docx, txt',
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

