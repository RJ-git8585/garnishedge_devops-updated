from rest_framework import status
from processor.models.garnishment_fees import GarnishmentFeesRules
from processor.garnishment_library.utils.response import ResponseHelper
from processor.serializers.garnishment_fees_serializers import GarnishmentFeesRulesSerializer
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


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
                return ResponseHelper.success_response('Rule data fetched successfully', serializer.data)
            else:
                rules = GarnishmentFeesRules.objects.all()
                serializer = GarnishmentFeesRulesSerializer(
                    rules, many=True)
                return ResponseHelper.success_response('All rules fetched successfully', serializer.data)
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(f'Rule "{rule}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHelper.error_response('Failed to fetch data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                return ResponseHelper.success_response('Rule created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return ResponseHelper.error_response('Rule is required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule_obj = GarnishmentFeesRules.objects.get(rule=rule)
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(f'Rule "{rule}" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = GarnishmentFeesRulesSerializer(
                rule_obj, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Rule updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return ResponseHelper.error_response('Rule is required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            rule_obj = GarnishmentFeesRules.objects.get(rule=rule)
            rule_obj.delete()
            return ResponseHelper.success_response(f'Rule "{rule}" deleted successfully')
        except GarnishmentFeesRules.DoesNotExist:
            return ResponseHelper.error_response(f'Rule "{rule}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
