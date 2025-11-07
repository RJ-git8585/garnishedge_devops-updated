import logging
from rest_framework import status
from datetime import date
from django.db.models import Q
from processor.models.garnishment_fees import GarnishmentFeesRules, GarnishmentFees
from processor.garnishment_library.utils.response import ResponseHelper
from processor.serializers.garnishment_fees_serializers import GarnishmentFeesRulesSerializer, GarnishmentFeesSerializer
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

logger = logging.getLogger(__name__)


class GarnishmentFeesRules(APIView):
    """
    API view for CRUD operations on garnishment fees rules.
    Provides robust exception handling and clear response messages.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', GarnishmentFeesRulesSerializer(many=True)),
            404: 'Rule not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, rule=None):
        """
        Retrieve a specific garnishment fee rule by Rule or all rules if Rule is not provided.
        """
        try:
            if rule:
                rule_obj = GarnishmentFeesRules.objects.get(rule__iexact=rule)
                serializer = GarnishmentFeesRulesSerializer(rule_obj)
                return ResponseHelper.success_response(
                    message="Rule data fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                rules = GarnishmentFeesRules.objects.all()
                serializer = GarnishmentFeesRulesSerializer(rules, many=True)
                return ResponseHelper.success_response(
                    message="All rules fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(
                message=f'Rule "{rule}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return ResponseHelper.error_response(
                message="Failed to fetch data",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentFeesRulesSerializer,
        responses={
            201: openapi.Response('Created', GarnishmentFeesRulesSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new garnishment fee rule.
        """
        try:
            serializer = GarnishmentFeesRulesSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Rule created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    message="Validation failed",
                    error=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Error creating GarnishmentFeesRules")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentFeesRulesSerializer,
        responses={
            200: openapi.Response('Updated', GarnishmentFeesRulesSerializer),
            400: 'Invalid data',
            404: 'Rule not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, rule=None):
        """
        Update an existing garnishment fee rule by Rule.
        """
        if not rule:
            return ResponseHelper.error_response(
                message="Rule is required in URL to update data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            rule_obj = GarnishmentFeesRules.objects.get(rule=rule)
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(
                message=f'Rule "{rule}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        try:
            serializer = GarnishmentFeesRulesSerializer(rule_obj, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Rule updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                return ResponseHelper.error_response(
                    message="Validation failed",
                    error=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Error updating GarnishmentFeesRules")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'Rule deleted successfully',
            400: 'Rule is required in URL to delete data',
            404: 'Rule not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, rule=None):
        """
        Delete a garnishment fee rule by Rule.
        """
        if not rule:
            return ResponseHelper.error_response(
                message="Rule is required in URL to delete data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        try:
            rule_obj = GarnishmentFeesRules.objects.get(rule=rule)
            rule_obj.delete()
            return ResponseHelper.success_response(
                message=f'Rule "{rule}" deleted successfully',
                status_code=status.HTTP_200_OK
            )
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(
                message=f'Rule "{rule}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error deleting GarnishmentFeesRules")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------- CRUD API for GarnishmentFees --------
class GarnishmentFeesAPIView(APIView):
    """
    API view for CRUD operations on GarnishmentFees.
    Supports:
    - GET /rules/ - List all fees (with optional filtering)
    - GET /rules/<pk>/ - Retrieve a specific fee by ID
    - POST /rules/ - Create a new fee
    - PUT /rules/<pk>/ - Update a fee by ID
    - DELETE /rules/<pk>/ - Delete a fee by ID
    """
    
    def get_queryset(self, include_inactive=False):
        """
        Get queryset filtered by effective_date and is_active.
        By default, only returns active fees with effective_date <= today or null.
        """
        today = date.today()
        queryset = GarnishmentFees.objects.select_related('state', 'garnishment_type', 'pay_period', 'rule')
        
        if not include_inactive:
            queryset = queryset.filter(
                is_active=True
            ).filter(Q(effective_date__isnull=True) | Q(effective_date__lte=today))
        
        return queryset
    
    def get_object(self, pk):
        """Get a specific GarnishmentFees instance by pk."""
        try:
            return self.get_queryset().get(pk=pk)
        except GarnishmentFees.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', GarnishmentFeesSerializer(many=True)),
            500: 'Internal server error'
        }
    )
    def get(self, request, pk=None):
        """
        Retrieve all fees or a specific fee by ID.
        Query params:
        - include_inactive: Set to 'true' to include inactive fees
        """
        try:
            include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
            
            if pk:
                # Retrieve single record
                instance = self.get_object(pk)
                if not instance:
                    return ResponseHelper.error_response(
                        message="GarnishmentFees not found",
                        status_code=status.HTTP_404_NOT_FOUND
                    )
                serializer = GarnishmentFeesSerializer(instance)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                # Retrieve all records
                queryset = self.get_queryset(include_inactive=include_inactive)
                serializer = GarnishmentFeesSerializer(queryset, many=True)
                return ResponseHelper.success_response(
                    message="All records fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
        except Exception as e:
            logger.exception("Error retrieving GarnishmentFees")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentFeesSerializer,
        responses={
            201: openapi.Response('Created', GarnishmentFeesSerializer),
            400: 'Validation failed',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new garnishment fee.
        """
        try:
            serializer = GarnishmentFeesSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    message="Validation failed",
                    error=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Error creating GarnishmentFees")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=GarnishmentFeesSerializer,
        responses={
            200: openapi.Response('Updated', GarnishmentFeesSerializer),
            400: 'Validation failed',
            404: 'Record not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pk=None):
        """
        Update a garnishment fee by ID.
        """
        if not pk:
            return ResponseHelper.error_response(
                message="ID is required in URL to update data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            instance = self.get_object(pk)
            if not instance:
                return ResponseHelper.error_response(
                    message="GarnishmentFees not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            serializer = GarnishmentFeesSerializer(instance, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                return ResponseHelper.error_response(
                    message="Validation failed",
                    error=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Error updating GarnishmentFees")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'Record deleted successfully',
            400: 'ID is required in URL to delete data',
            404: 'Record not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk=None):
        """
        Delete a garnishment fee by ID.
        """
        if not pk:
            return ResponseHelper.error_response(
                message="ID is required in URL to delete data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            instance = self.get_object(pk)
            if not instance:
                return ResponseHelper.error_response(
                    message="GarnishmentFees not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            instance.delete()
            return ResponseHelper.success_response(
                message="Record deleted successfully",
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Error deleting GarnishmentFees")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# -------- READ (by filters) --------
class GarnishmentFeesListByFilterAPI(APIView):
    """
    API view for filtering GarnishmentFees by state, pay_period, and garnishment_type.
    """
    serializer_class = GarnishmentFeesSerializer

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', GarnishmentFeesSerializer(many=True)),
            404: 'No matching record found',
            500: 'Internal server error'
        }
    )
    def get(self, request, state, pay_period, garnishment_type_name):
        try:
            today = date.today()
            fees = GarnishmentFees.objects.filter(
                state__state__iexact=state,
                pay_period__name__iexact=pay_period,
                garnishment_type__type__iexact=garnishment_type_name,
                is_active=True
            ).filter(Q(effective_date__isnull=True) | Q(effective_date__lte=today))
            
            if not fees.exists():
                return ResponseHelper.error_response(
                    message="No matching record found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            serializer = GarnishmentFeesSerializer(fees, many=True)
            return ResponseHelper.success_response(
                message="Fees fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Error fetching GarnishmentFees by filter")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )