from rest_framework import status
from processor.models import (CreditorDebtAppliedRule,
                      CreditorDebtRule, CreditorDebtExemptAmtConfig, CreditorDebtRuleEditPermission)
from django.core.exceptions import ValidationError
from processor.garnishment_library.utils.response import ResponseHelper
import logging
from processor.serializers import (CreditorDebtAppliedRulesSerializers,
                           CreditorDebtRuleSerializers, CreditorDebtExemptAmtConfigSerializers, CreditorDebtRuleEditPermissionSerializers)
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from processor.garnishment_library.utils import StateAbbreviations
from drf_yasg import openapi
logger = logging.getLogger(__name__)


class CreditorDebtAppliedRuleAPIView(APIView):
    """
    API view to get applied creditor debt rule by case_i d.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Creditor debt applied rule data fetched successfully', CreditorDebtAppliedRulesSerializers),
            404: 'case_id not found',
            400: 'Invalid input provided',
            500: 'Internal server error'
        }
    )
    def get(self, request, case_id):
        try:
            rule = CreditorDebtAppliedRule.objects.get(case_id=case_id)
            serializer = CreditorDebtAppliedRulesSerializers(rule)
            return ResponseHelper.success_response(
                f'Data for case_id "{case_id}" fetched successfully',
                serializer.data
            )
        except CreditorDebtAppliedRule.DoesNotExist:
            return ResponseHelper.error_response(
                f'case_id "{case_id}" not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except ValidationError:
            return ResponseHelper.error_response(
                "Invalid input provided",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return ResponseHelper.error_response(
                "An unexpected error occurred",
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreditorDebtRuleAPIView(APIView):
    """
    API view for CRUD operations on creditor debt rules by state.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Creditor debt rule data fetched successfully', CreditorDebtRuleSerializers(many=True)),
            404: 'State not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, state=None, pk=None):
        try:
            if pk is not None:
                try:
                    rule = CreditorDebtRule.objects.get(id=pk)
                    serializer = CreditorDebtRuleSerializers(rule)
                    return ResponseHelper.success_response(f'Data for id "{pk}" fetched successfully', serializer.data)
                except CreditorDebtRule.DoesNotExist:
                    return ResponseHelper.error_response(f'id "{pk}" not found', status_code=status.HTTP_404_NOT_FOUND)
            elif state:
                state = StateAbbreviations(
                    state.strip()).get_state_name_and_abbr()
                try:
                    rule = CreditorDebtRule.objects.get(
                        state__state__iexact=state.strip())
                    serializer = CreditorDebtRuleSerializers(rule)
                    return ResponseHelper.success_response(f'Data for state "{state}" fetched successfully', serializer.data)
                except CreditorDebtRule.DoesNotExist:
                    return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
            else:
                rules = CreditorDebtRule.objects.all()
                serializer = CreditorDebtRuleSerializers(rules, many=True)
                return ResponseHelper.success_response('All data fetched successfully', serializer.data)
        except ValidationError as e:
            return ResponseHelper.error_response(f"Invalid input: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in GET method")
            return ResponseHelper.error_response("An unexpected error occurred.", str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=CreditorDebtRuleSerializers,
        responses={
            201: openapi.Response('Creditor debt rule created successfully', CreditorDebtRuleSerializers),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            serializer = CreditorDebtRuleSerializers(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating CreditorDebtRule")
            return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=CreditorDebtRuleSerializers,
        responses={
            200: openapi.Response('Creditor debt rule updated successfully', CreditorDebtRuleSerializers),
            400: 'State and pay_period are required in URL to update data or invalid data',
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, state=None):
        if not state:
            return ResponseHelper.error_response('State and pay_period are required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            state = StateAbbreviations(
                state.strip()).get_state_name_and_abbr().lower()
            rule = CreditorDebtRule.objects.get(state__state__iexact=state)
        except CreditorDebtRule.DoesNotExist:
            return ResponseHelper.error_response(f'Data for state "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = CreditorDebtRuleSerializers(rule, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating CreditorDebtRule")
            return ResponseHelper.error_response('Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        responses={
            200: 'Creditor debt rule deleted successfully',
            400: 'State and pay_period are required in URL to delete data',
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, state=None):
        if not state:
            return ResponseHelper.error_response('State and pay_period are required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule = CreditorDebtRule.objects.get(state__state__iexact=state)
            rule.delete()
            return ResponseHelper.success_response(f'Data for state "{state}" deleted successfully')
        except CreditorDebtRule.DoesNotExist:
            return ResponseHelper.error_response(f'Data for state "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting CreditorDebtRule")
            return ResponseHelper.error_response('Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreditorDebtExemptAmtConfigAPIView(APIView):
    """
    API view for CRUD operations on creditor debt exempt amount configuration.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Creditor debt exempt amount config data fetched successfully', CreditorDebtExemptAmtConfigSerializers(many=True)),
            404: 'State or pay_period not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self, request, pay_period=None, state=None):
        try:
            if state and pay_period:
                state = StateAbbreviations(
                    state.strip()).get_state_name_and_abbr()
                rule_qs = CreditorDebtExemptAmtConfig.objects.filter(
                    state__iexact=state.strip(), pay_period__iexact=pay_period.lower()
                )
                if not rule_qs.exists():
                    return ResponseHelper.error_response(
                        f'No data found for state "{state}" and pay_period "{pay_period}".',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
                serializer = CreditorDebtExemptAmtConfigSerializers(
                    rule_qs, many=True)
                return ResponseHelper.success_response(
                    f'Data for state "{state}" and pay_period "{pay_period}" fetched successfully.',
                    serializer.data
                )
            elif state:
                state = StateAbbreviations(
                    state.strip()).get_state_name_and_abbr()
                rule_qs = CreditorDebtExemptAmtConfig.objects.filter(
                    state__iexact=state.strip())
                if not rule_qs.exists():
                    return ResponseHelper.error_response(
                        f'State "{state}" not found',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
                serializer = CreditorDebtExemptAmtConfigSerializers(
                    rule_qs, many=True)
                return ResponseHelper.success_response(
                    f'Data for state "{state}" fetched successfully',
                    serializer.data
                )
            else:
                rules = CreditorDebtExemptAmtConfig.objects.all()
                serializer = CreditorDebtExemptAmtConfigSerializers(
                    rules, many=True)
                return ResponseHelper.success_response(
                    'All data fetched successfully',
                    serializer.data
                )
        except ValidationError as e:
            return ResponseHelper.error_response(
                f"Invalid input: {str(e)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(
                "Unexpected error in GET method of CreditorDebtExemptAmtConfigAPIView")
            return ResponseHelper.error_response(
                "An unexpected error occurred.",
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=CreditorDebtExemptAmtConfigSerializers,
        responses={
            201: openapi.Response('Creditor debt exempt amount config created successfully', CreditorDebtExemptAmtConfigSerializers),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            serializer = CreditorDebtExemptAmtConfigSerializers(
                data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating CreditorDebtExemptAmtConfig")
            return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=CreditorDebtExemptAmtConfigSerializers,
        responses={
            200: openapi.Response('Creditor debt exempt amount config updated successfully', CreditorDebtExemptAmtConfigSerializers),
            400: 'State and pay_period are required in URL to update data or invalid data',
            404: 'State or pay_period not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, pay_period=None, state=None):
        if not (state and pay_period):
            return ResponseHelper.error_response('State and pay_period are required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule = CreditorDebtExemptAmtConfig.objects.get(
                state__iexact=state, pay_period__iexact=pay_period)
        except CreditorDebtExemptAmtConfig.DoesNotExist:
            return ResponseHelper.error_response(f'Data for state "{state}" and pay_period "{pay_period}" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = CreditorDebtExemptAmtConfigSerializers(
                rule, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating CreditorDebtExemptAmtConfig")
            return ResponseHelper.error_response('Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        responses={
            200: 'Creditor debt exempt amount config deleted successfully',
            400: 'State and pay_period are required in URL to delete data',
            404: 'State or pay_period not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pay_period=None, state=None):
        if not (state and pay_period):
            return ResponseHelper.error_response('State and pay_period are required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule = CreditorDebtExemptAmtConfig.objects.get(
                state__iexact=state, pay_period__iexact=pay_period)
            rule.delete()
            return ResponseHelper.success_response(f'Data for state "{state}" and pay_period "{pay_period}" deleted successfully')
        except CreditorDebtExemptAmtConfig.DoesNotExist:
            return ResponseHelper.error_response(f'Data for state "{state}" and pay_period "{pay_period}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error deleting CreditorDebtExemptAmtConfig")
            return ResponseHelper.error_response('Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreditorDebtEditPermissionAPIView(APIView):
    """
    API view for CRUD operations on creditor debt rule edit permissions.
    """

    @swagger_auto_schema(
        request_body=CreditorDebtRuleEditPermissionSerializers,
        responses={
            201: openapi.Response('Creditor debt rule edit permission created successfully', CreditorDebtRuleEditPermissionSerializers),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            serializer = CreditorDebtRuleEditPermissionSerializers(
                data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Creditor debt rule edit permission data fetched successfully', CreditorDebtRuleEditPermissionSerializers(many=True)),
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, state=None):
        try:
            if state:
                try:
                    state = StateAbbreviations(
                        state.strip()).get_state_name_and_abbr().title()
                    rule = CreditorDebtRuleEditPermission.objects.get(
                        state__iexact=state)
                    serializer = CreditorDebtRuleEditPermissionSerializers(
                        rule)
                    return ResponseHelper.success_response(f'Data for state "{state}" fetched successfully', serializer.data)
                except CreditorDebtRuleEditPermission.DoesNotExist:
                    return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
            else:
                rules = CreditorDebtRuleEditPermission.objects.all()
                serializer = CreditorDebtRuleEditPermissionSerializers(
                    rules, many=True)
                return ResponseHelper.success_response('All data fetched successfully', serializer.data)
        except Exception as e:
            return ResponseHelper.error_response('Failed to fetch data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
