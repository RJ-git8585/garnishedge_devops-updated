from rest_framework.views import APIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from datetime import date
from processor.models import ExemptConfig, GarnishmentType, ExemptRule, ThresholdCondition
from processor.serializers import ExemptConfigWithThresholdSerializer, get_garnishment_type_serializer, get_garnishment_type_rule_serializer, BaseGarnishmentTypeExemptRuleSerializer, CreditorDebtExemptRuleSerializer, ThresholdConditionSerializer
from processor.garnishment_library import ResponseHelper
import logging
from rest_framework.response import Response

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

    def get_queryset(self, garnishment_type=None, include_inactive=False):
        """
        Get queryset filtered by garnishment type if provided.
        By default, only returns active configs with effective_date <= today or null.
        Set include_inactive=True to get all configs regardless of active status.
        """
        queryset = ExemptConfig.objects.select_related('state', 'pay_period', 'garnishment_type')
        
        # Apply effective date filtering unless include_inactive is True
        if not include_inactive:
            today = date.today()
            queryset = queryset.filter(
                is_active=True
            ).filter(Q(effective_date__isnull=True) | Q(effective_date__lte=today))
        
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
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            elif rule_id:
                # Get records by rule_id
                queryset = self.get_queryset(garnishment_type)
                configs = queryset.filter(rule_id=rule_id)
                if not configs.exists():
                    return ResponseHelper.error_response(
                        message="No ExemptConfig found for the given rule_id",
                        status_code=status.HTTP_404_NOT_FOUND
                    )
                serializer = serializer_class(configs, many=True)
                return ResponseHelper.success_response(
                    message="Records fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                # Get all records (filtered by garnishment type if provided)
                queryset = self.get_queryset(garnishment_type)
                serializer = serializer_class(queryset, many=True)
                return ResponseHelper.success_response(
                    message="All data fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
                
        except ValueError as e:
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except ExemptConfig.DoesNotExist:
            return ResponseHelper.error_response(
                message="ExemptConfig not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _deactivate_previous_configs(self, new_config):
        """
        Deactivate previous configs that should be inactive when a new config becomes effective.
        This happens when:
        1. New config has an effective_date
        2. There are existing active configs with same key fields (state, pay_period, garnishment_type, etc.)
        3. On the effective_date, previous configs should be marked inactive
        """
        try:
            # Find configs that should be deactivated based on matching criteria
            # Match by key fields: state, pay_period, garnishment_type, debt_type, home_state, ftb_type
            matching_configs = ExemptConfig.objects.filter(
                state=new_config.state,
                pay_period=new_config.pay_period,
                garnishment_type=new_config.garnishment_type,
                is_active=True
            ).exclude(id=new_config.id)
            
            # Match optional fields if they exist in new config
            if new_config.debt_type:
                matching_configs = matching_configs.filter(debt_type=new_config.debt_type)
            if new_config.home_state:
                matching_configs = matching_configs.filter(home_state=new_config.home_state)
            if new_config.ftb_type:
                matching_configs = matching_configs.filter(ftb_type=new_config.ftb_type)
            
            # If new config has an effective_date in the future, schedule deactivation
            # If effective_date is today or past, deactivate immediately
            if new_config.effective_date:
                today = date.today()
                if new_config.effective_date <= today:
                    # Effective date has passed or is today, deactivate previous configs now
                    count = matching_configs.update(is_active=False)
                    if count > 0:
                        logger.info(f"Deactivated {count} previous config(s) for config ID {new_config.id}")
            
        except Exception as e:
            logger.exception(f"Error deactivating previous configs for config ID {new_config.id}: {e}")
            # Don't fail the request if deactivation fails, just log it

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def post(self, request, garnishment_type=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            serializer = serializer_class(data=request.data)
            
            if serializer.is_valid():
                # Use transaction.atomic() to ensure all-or-nothing behavior
                # If any part fails (ExemptConfig or ThresholdAmount creation), 
                # the entire operation will be rolled back
                with transaction.atomic():
                    instance = serializer.save()
                    # Handle effective date logic - deactivate previous configs if needed
                    # This is also within the transaction, so if it fails, everything rolls back
                    # Note: If deactivation fails, the exception will propagate and roll back the transaction
                    try:
                        self._deactivate_previous_configs(instance)
                    except Exception as e:
                        logger.exception(f"Error in _deactivate_previous_configs for config ID {instance.id}: {e}")
                        # Re-raise to ensure transaction rollback
                        raise
                
                return ResponseHelper.success_response(
                    message="Record created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        except ValueError as e:
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error creating ExemptConfig")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(request_body=ExemptConfigWithThresholdSerializer)
    def put(self, request, garnishment_type=None, pk=None):
        if not pk:
            return Response({"error": "pk required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            queryset = self.get_queryset(garnishment_type)
            config = queryset.get(pk=pk)
            
            serializer = serializer_class(config, data=request.data,partial=True)
            if serializer.is_valid():
                # Use transaction.atomic() to ensure all-or-nothing behavior
                # If any part fails (ExemptConfig or ThresholdAmount update), 
                # the entire operation will be rolled back
                with transaction.atomic():
                    serializer.save()
                
                return ResponseHelper.success_response(
                    message="Record updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        except ValueError as e:
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except ExemptConfig.DoesNotExist:
            return ResponseHelper.error_response(
                message="ExemptConfig not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error updating ExemptConfig")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, garnishment_type=None, pk=None):
        if not pk:
            return ResponseHelper.error_response(
                message="pk required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            queryset = self.get_queryset(garnishment_type)
            config = queryset.get(pk=pk)
            config.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except ExemptConfig.DoesNotExist:
            return ResponseHelper.error_response(
                message="ExemptConfig not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error deleting ExemptConfig")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
                type_mapping = {
                    'creditor_debt': 'Creditor_Debt',
                    'state_tax_levy': 'State_Tax_Levy',
                }
                actual_type_name = type_mapping.get(garnishment_type) or type_mapping.get(garnishment_type.lower())

                if not actual_type_name:
                    try:
                        garnishment_type_obj = GarnishmentType.objects.get(type=garnishment_type)
                    except GarnishmentType.DoesNotExist:
                        try:
                            garnishment_type_obj = GarnishmentType.objects.get(type__iexact=garnishment_type)
                        except GarnishmentType.DoesNotExist:
                            raise ValueError(f"Unsupported garnishment type: {garnishment_type}")
                else:
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
                queryset = self.get_queryset(garnishment_type)
                rule = queryset.get(pk=pk)
                serializer = serializer_class(rule)
                return ResponseHelper.success_response(
                    message="Record fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            else:
                queryset = self.get_queryset(garnishment_type)
                serializer = serializer_class(queryset, many=True)
                return ResponseHelper.success_response(
                    message="All data fetched successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )

        except ValueError as e:
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return ResponseHelper.error_response("ExemptRule not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in GET")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=CreditorDebtExemptRuleSerializer)
    def post(self, request, garnishment_type=None):
        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            serializer = serializer_class(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except ValueError as e:
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating ExemptRule")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(request_body=CreditorDebtExemptRuleSerializer)
    def put(self, request, garnishment_type=None, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            serializer_class = self.get_serializer_class(garnishment_type)
            queryset = self.get_queryset(garnishment_type)
            rule = queryset.get(pk=pk)

            serializer = serializer_class(rule, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Record updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            return ResponseHelper.error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except ValueError as e:
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return ResponseHelper.error_response("ExemptRule not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error updating ExemptRule")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, garnishment_type=None, pk=None):
        if not pk:
            return ResponseHelper.error_response("pk required", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            queryset = self.get_queryset(garnishment_type)
            rule = queryset.get(pk=pk)
            rule.delete()
            return ResponseHelper.success_response(
                message="Deleted successfully",
                data={},
                status_code=status.HTTP_200_OK
            )

        except ValueError as e:
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except ExemptRule.DoesNotExist:
            return ResponseHelper.error_response("ExemptRule not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting ExemptRule")
            return ResponseHelper.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
