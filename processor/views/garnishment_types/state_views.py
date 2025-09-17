from processor.models import State

from processor.garnishment_library.utils.response import ResponseHelper
import logging
from django.core.exceptions import ValidationError
from processor.garnishment_library.utils import StateAbbreviations
from processor.serializers import StateSerializer
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
logger = logging.getLogger(__name__)

class StateAPIView(APIView):
    """
    API view for CRUD operations on state.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('State data fetched successfully', StateSerializer),
            404: 'State not found',
            400: 'Invalid input',
            500: 'Internal server error'
        }
    )
    def get(self,request, state=None):
        """
        Retrieve state data for a specific state or all states.
        """
        try:
            if state:
                # Get the full state name from abbreviation, if needed
                state_name = StateAbbreviations(state.strip()).get_state_name_and_abbr()

                try:
                    # Fetch the state using the name (case insensitive)
                    rule = State.objects.get(state__iexact=state_name.strip())
                    serializer = StateSerializer(rule)
                    return ResponseHelper.success_response(
                        f'Data for state "{state_name}" fetched successfully', serializer.data
                    )
                except State.DoesNotExist:
                    return ResponseHelper.error_response(
                        f'State "{state_name}" not found', status_code=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Retrieve all states if 'state' is not provided
                rules = State.objects.all()
                serializer = StateSerializer(rules, many=True)
                return ResponseHelper.success_response('All states data fetched successfully', serializer.data)

        except ValidationError as e:
            return ResponseHelper.error_response(
                f'Invalid input: {str(e)}', status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Unexpected error in GET method of StateAPIView")
            return ResponseHelper.error_response(
                'Failed to fetch state data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    def post(self, request):
        """
        Create a new state .
        """
        try:
            serializer = StateSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    'Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED
                )
            else:
                return ResponseHelper.error_response(
                    'Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception("Unexpected error in POST method of StateAPIView")
            return ResponseHelper.error_response(
                'Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=StateSerializer,
        responses={
            200: openapi.Response('Data updated successfully', StateSerializer),
            400: 'State is required in URL or invalid data',
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, state=None):
        """
        Update state data for a specific state.
        """
        if not state:
            return ResponseHelper.error_response('State is required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)

        try:
            # Retrieve the full state name from abbreviation or name
            state_name = StateAbbreviations(state.strip()).get_state_name_and_abbr()
            rule = State.objects.get(state__iexact=state_name.strip())
        except ValueError as ve:
            return ResponseHelper.error_response(str(ve), status_code=status.HTTP_404_NOT_FOUND)
        except State.DoesNotExist:
            return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
        
        try:
            serializer = StateSerializer(rule, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error updating StateSerializer")
            return ResponseHelper.error_response(
                'Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        responses={
            200: 'State data deleted successfully',
            400: 'State is required in URL to delete data',
            404: 'State not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, state=None):
        """
        Delete state data for a specific state.
        """
        if not state:
            return ResponseHelper.error_response('State is required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)

        try:
            state_name = StateAbbreviations(state.strip()).get_state_name_and_abbr()
            rule = State.objects.get(state__iexact=state_name.strip())
            rule.delete()
            return ResponseHelper.success_response(f'Data for state "{state_name}" deleted successfully')
        except ValueError as ve:
            return ResponseHelper.error_response(str(ve), status_code=status.HTTP_404_NOT_FOUND)
        except State.DoesNotExist:
            return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Unexpected error in DELETE method of StateAPIView")
            return ResponseHelper.error_response(
                'Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    # def post(self, request):
    #     """
    #     Create a new state tax levy config.
    #     """
    #     try:
    #         serializer = StateSerializer(data=request.data)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return ResponseHelper.success_response('Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
    #         else:
    #             return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
    #     except Exception as e:
    #         logger.exception(
    #             "Unexpected error in POST method of StateAPIView")
    #         return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # @swagger_auto_schema(
    #     request_body=StateSerializer,
    #     responses={
    #         200: openapi.Response('Data updated successfully', StateSerializer),
    #         400: 'State and pay_period are required in URL to update data or invalid data',
    #         404: 'State not found',
    #         500: 'Internal server error'
    #     }
    # )
    # def put(self, request, state=None):
    #     """
    #     Update state data for a specific state.
    #     """
    #     if not state:
    #         return ResponseHelper.error_response('State and pay_period are required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)
    #     try:
    #         state = StateAbbreviations(
    #             state.strip()).get_state_name_and_abbr().lower()
    #         rule = State.objects.get(state__iexact=state)
    #     except State.DoesNotExist:
    #         rule = State.objects.get(state__iexact=state)
    #     except State.DoesNotExist:
    #         return ResponseHelper.error_response(f'Data for state "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
    #     try:
    #         serializer = StateSerializer(rule, data=request.data)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return ResponseHelper.success_response('Data updated successfully', serializer.data)
    #         else:
    #             return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
    #     except Exception as e:
    #         logger.exception("Error updating StateSerializer")
    #         return ResponseHelper.error_response('Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # @swagger_auto_schema(
    #     responses={
    #         200: 'State data deleted successfully',
    #         400: 'State is required in URL to delete data',
    #         404: 'State not found',
    #         500: 'Internal server error'
    #     }
    # )
    # def delete(self, request, state=None):
    #     """
    #     Delete state data for a specific state.
    #     """
    #     if not state:
    #         return ResponseHelper.error_response('State is required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)
    #     try:
    #         state = State.objects.get(
    #             state__iexact=state)
    #         state.delete()
    #         return ResponseHelper.success_response(f'Data for state "{state}" deleted successfully')
    #     except State.DoesNotExist:
    #         return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
    #     except Exception as e:
    #         logger.exception(
    #             "Unexpected error in DELETE method of StateAPIView")
    #         return ResponseHelper.error_response('Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # def get(self, request, state=None):
    #     """
    #     Retrieve state data for a specific state or all states.
    #     """
    #     try:
    #         if state:
    #             # Get the full state name from abbreviation, if needed
    #             state_name, state_abbr = StateAbbreviations(state.strip()).get_state_name_and_abbr()

    #             try:
    #                 # Fetch the state using the name or abbreviation
    #                 rule = State.objects.get(state__iexact=state_name.strip())
    #                 serializer = StateSerializer(rule)
    #                 return ResponseHelper.success_response(
    #                     f'Data for state "{state_name}" fetched successfully', serializer.data
    #                 )
    #             except State.DoesNotExist:
    #                 return ResponseHelper.error_response(
    #                     f'State "{state_name}" not found', status_code=status.HTTP_404_NOT_FOUND
    #                 )
    #         else:
    #             # Retrieve all states
    #             rules = State.objects.all()
    #             serializer = StateSerializer(rules, many=True)
    #             return ResponseHelper.success_response('All states data fetched successfully', serializer.data)

    #     except ValidationError as e:
    #         return ResponseHelper.error_response(
    #             f'Invalid input: {str(e)}', status_code=status.HTTP_400_BAD_REQUEST
    #         )
    #     except Exception as e:
    #         logger.exception("Unexpected error in GET method of StateAPIView")
    #         return ResponseHelper.error_response(
    #             'Failed to fetch state data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )


    # def get(self, request, state=None):
    #     """
    #     Retrieve state data for a specific state or all states.
    #     """
    #     try:
    #         if state:
    #             state = StateAbbreviations(
    #                 state.strip()).get_state_name_and_abbr()
    #             try:
    #                 rule = State.objects.get(
    #                     state__iexact=state.strip())
    #                 serializer = StateSerializer(rule)
    #                 return ResponseHelper.success_response(f'Data for state "{state}" fetched successfully', serializer.data)
    #             except State.DoesNotExist:
    #                 return ResponseHelper.error_response(f'State "{state}" not found', status_code=status.HTTP_404_NOT_FOUND)
    #         else:
    #             rules = State.objects.all()
    #             rules = State.objects.all()
    #             serializer = StateSerializer(rules, many=True)
    #             return ResponseHelper.success_response('All data fetched successfully', serializer.data)
    #     except ValidationError as e:
    #         return ResponseHelper.error_response(f"Invalid input: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
    #     except Exception as e:
    #         logger.exception(
    #             "Unexpected error in GET method of StateAPIView")
    #         return ResponseHelper.error_response('Failed to fetch data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
