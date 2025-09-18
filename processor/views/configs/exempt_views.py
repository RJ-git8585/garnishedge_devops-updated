from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from processor.models import ExemptConfig, GarnishmentType, ExemptRule
from processor.serializers import ExemptConfigWithThresholdSerializer, get_garnishment_type_serializer, get_garnishment_type_rule_serializer, BaseGarnishmentTypeExemptRuleSerializer, CreditorDebtExemptRuleSerializer
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

class ExemptConfigAPIView(APIView):
    """
    API view for CRUD operations on ExemptConfig with dynamic garnishment type support.
    Supports URLs like:
    - /config/creditor_debt/ - CRUD for Creditor_debt garnishment type
    - /config/state_tax_levy/ - CRUD for State_tax_levy garnishment type
    """

    def get_serializer_class(self, garnishment_type=None):
        """
        Get the appropriate serializer class based on garnishment type.
        If no garnishment_type is provided, use the default serializer.
        """
        if garnishment_type:
            try:
                return get_garnishment_type_serializer(garnishment_type)
            except ValueError as e:
                logger.error(f"Invalid garnishment type: {garnishment_type}")
                raise ValueError(str(e))
        return ExemptConfigWithThresholdSerializer

    def get_queryset(self, garnishment_type=None):
        """
        Get queryset filtered by garnishment type if provided.
        """
        queryset = ExemptConfig.objects.select_related('state', 'pay_period', 'garnishment_type')
        
        if garnishment_type:
            try:
                # Map URL parameter to actual GarnishmentType names
                # Handle various case combinations that users might use
                type_mapping = {
                    'creditor_debt': 'Creditor_Debt',
                    'state_tax_levy': 'State_Tax_Levy',
                }
                
                # Try exact match first, then lowercase match
                actual_type_name = type_mapping.get(garnishment_type) or type_mapping.get(garnishment_type.lower())
                
                if not actual_type_name:
                    # If no mapping found, try to find the GarnishmentType directly
                    try:
                        garnishment_type_obj = GarnishmentType.objects.get(type=garnishment_type)
                    except GarnishmentType.DoesNotExist:
                        # Try case-insensitive search
                        try:
                            garnishment_type_obj = GarnishmentType.objects.get(type__iexact=garnishment_type)
                        except GarnishmentType.DoesNotExist:
                            raise ValueError(f"Unsupported garnishment type: {garnishment_type}")
                else:
                    # Get the GarnishmentType object using the mapped name
                    garnishment_type_obj = GarnishmentType.objects.get(type=actual_type_name)
                queryset = queryset.filter(garnishment_type=garnishment_type_obj)
            except GarnishmentType.DoesNotExist:
                logger.error(f"GarnishmentType '{garnishment_type}' does not exist")
                raise ValueError(f"GarnishmentType '{garnishment_type}' does not exist")
        
        return queryset

    @swagger_auto_schema(
        responses={
            200: openapi.Response("ExemptConfig data fetched successfully", ExemptConfigWithThresholdSerializer(many=True)),
            404: "ExemptConfig not found",
            400: "Invalid garnishment type",
            500: "Internal server error"
        }
    )
    def get(self, request, garnishment_type=None, pk=None, rule_id=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            
            if pk:
                # Get specific record by primary key
                queryset = self.get_queryset(garnishment_type)
                config = queryset.get(pk=pk)
                serializer = serializer_class(config)
                return Response(serializer.data, status=status.HTTP_200_OK)
            elif rule_id:
                # Get records by rule_id
                queryset = self.get_queryset(garnishment_type)
                configs = queryset.filter(rule_id=rule_id)
                if not configs.exists():
                    return Response({"error": "No ExemptConfig found for the given rule_id"}, status=status.HTTP_404_NOT_FOUND)
                serializer = serializer_class(configs, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                # Get all records (filtered by garnishment type if provided)
                queryset = self.get_queryset(garnishment_type)
                serializer = serializer_class(queryset, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ExemptConfig.DoesNotExist:
            return Response({"error": "ExemptConfig not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def post(self, request, garnishment_type=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            serializer = serializer_class(data=request.data)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating ExemptConfig")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def put(self, request, garnishment_type=None, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            queryset = self.get_queryset(garnishment_type)
            config = queryset.get(pk=pk)
            
            serializer = serializer_class(config, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ExemptConfig.DoesNotExist:
            return Response({"error": "ExemptConfig not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating ExemptConfig")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, garnishment_type=None, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            queryset = self.get_queryset(garnishment_type)
            config = queryset.get(pk=pk)
            config.delete()
            return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
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


class ExemptRuleAPIView(APIView):
    """
    API view for CRUD operations on ExemptRule with dynamic garnishment type support.
    Supports URLs like:
    - /rule/creditor_debt/ - CRUD for Creditor_debt garnishment type
    - /rule/state_tax_levy/ - CRUD for State_tax_levy garnishment type
    """

    def get_serializer_class(self, garnishment_type=None):
        """
        Get the appropriate serializer class based on garnishment type.
        If no garnishment_type is provided, use the default serializer.
        """
        if garnishment_type:
            try:
                return get_garnishment_type_rule_serializer(garnishment_type)
            except ValueError as e:
                logger.error(f"Invalid garnishment type: {garnishment_type}")
                raise ValueError(str(e))
        # Default serializer for ExemptRule
        return BaseGarnishmentTypeExemptRuleSerializer

    def get_queryset(self, garnishment_type=None):
        """
        Get queryset filtered by garnishment type if provided.
        """
        queryset = ExemptRule.objects.select_related('state', 'garnishment_type')
        
        if garnishment_type:
            try:
                # Map URL parameter to actual GarnishmentType names
                # Handle various case combinations that users might use
                type_mapping = {
                    'creditor_debt': 'Creditor_Debt',
                    'state_tax_levy': 'State_Tax_Levy',
                }
                
                # Try exact match first, then lowercase match
                actual_type_name = type_mapping.get(garnishment_type) or type_mapping.get(garnishment_type.lower())
                
                if not actual_type_name:
                    # If no mapping found, try to find the GarnishmentType directly
                    try:
                        garnishment_type_obj = GarnishmentType.objects.get(type=garnishment_type)
                    except GarnishmentType.DoesNotExist:
                        # Try case-insensitive search
                        try:
                            garnishment_type_obj = GarnishmentType.objects.get(type__iexact=garnishment_type)
                        except GarnishmentType.DoesNotExist:
                            raise ValueError(f"Unsupported garnishment type: {garnishment_type}")
                else:
                    # Get the GarnishmentType object using the mapped name
                    garnishment_type_obj = GarnishmentType.objects.get(type=actual_type_name)
                queryset = queryset.filter(garnishment_type=garnishment_type_obj)
            except GarnishmentType.DoesNotExist:
                logger.error(f"GarnishmentType '{garnishment_type}' does not exist")
                raise ValueError(f"GarnishmentType '{garnishment_type}' does not exist")
        
        return queryset

    @swagger_auto_schema(
        responses={
            200: openapi.Response("ExemptRule data fetched successfully", CreditorDebtExemptRuleSerializer(many=True)),
            404: "ExemptRule not found",
            400: "Invalid garnishment type",
            500: "Internal server error"
        }
    )
    def get(self, request, garnishment_type=None, pk=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            
            if pk:
                # Get specific record by primary key
                queryset = self.get_queryset(garnishment_type)
                rule = queryset.get(pk=pk)
                serializer = serializer_class(rule)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                # Get all records (filtered by garnishment type if provided)
                queryset = self.get_queryset(garnishment_type)
                serializer = serializer_class(queryset, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return Response({"error": "ExemptRule not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=CreditorDebtExemptRuleSerializer)
    def post(self, request, garnishment_type=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            serializer = serializer_class(data=request.data)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating ExemptRule")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=CreditorDebtExemptRuleSerializer)
    def put(self, request, garnishment_type=None, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            queryset = self.get_queryset(garnishment_type)
            rule = queryset.get(pk=pk)
            
            serializer = serializer_class(rule, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return Response({"error": "ExemptRule not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating ExemptRule")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, garnishment_type=None, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            queryset = self.get_queryset(garnishment_type)
            rule = queryset.get(pk=pk)
            rule.delete()
            return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return Response({"error": "ExemptRule not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting ExemptRule")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)