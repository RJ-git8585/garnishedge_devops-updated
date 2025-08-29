from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import EmployerProfile
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from processor.garnishment_library.utils.response import ResponseHelper
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView
from ..serializers import EmployerProfileSerializer
from rest_framework.views import APIView


# Update Employer Details

class EmployerProfileEditView(RetrieveUpdateAPIView):
    """
    API view to retrieve and update employer profile details.
    """
    queryset = EmployerProfile.objects.all()
    serializer_class = EmployerProfileSerializer
    lookup_fields = ['id']

    def get_object(self):
        """
        Fetch the instance based on multiple lookup fields.
        """
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {field: self.kwargs[field]
                         for field in self.lookup_fields}
        obj = queryset.filter(**filter_kwargs).first()
        if not obj:
            raise Exception(f"Object not found with {filter_kwargs}")
        return obj

    @swagger_auto_schema(
        request_body=EmployerProfileSerializer,
        responses={
            200: 'Employer profile updated successfully',
            400: 'Invalid data',
            404: 'Employer not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, *args, **kwargs):
        """
        Update employer profile details.
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(
                instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            response_data = ResponseHelper.success_response(
                "Data updated Successfully", status_code=status.HTTP_200_OK)
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse(
                {'error': str(
                    e), "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmployerDetails(APIView):
    """
    API view for CRUD operations on employer profiles.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Employer data fetched successfully', EmployerProfileSerializer),
            404: 'Employer not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, id=None):
        """
        Retrieve employer profile(s).
        """
        try:
            if id:
                try:
                    employee = EmployerProfile.objects.get(id=id)
                    serializer = EmployerProfileSerializer(employee)
                    return ResponseHelper.success_response('Employer data fetched successfully', serializer.data)
                except EmployerProfile.DoesNotExist:
                    return ResponseHelper.error_response('Employer not found', status_code=status.HTTP_404_NOT_FOUND)
            else:
                employees = EmployerProfile.objects.all()
                serializer = EmployerProfileSerializer(employees, many=True)
                return ResponseHelper.success_response('All data fetched successfully', serializer.data)
        except Exception as e:
            return ResponseHelper.error_response('Failed to fetch data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=EmployerProfileSerializer,
        responses={
            201: openapi.Response('Employer profile created successfully', EmployerProfileSerializer),
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Create a new employer profile.
        """
        try:
            serializer = EmployerProfileSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data created successfully', serializer.data, status_code=status.HTTP_201_CREATED)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while creating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        request_body=EmployerProfileSerializer,
        responses={
            200: openapi.Response('Employer profile updated successfully', EmployerProfileSerializer),
            400: 'Invalid data or missing ID',
            404: 'Employer not found',
            500: 'Internal server error'
        }
    )
    def put(self, request, id=None):
        """
        Update an employer profile by ID.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to update data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            employee = EmployerProfile.objects.get(id=id)
        except EmployerProfile.DoesNotExist:
            return ResponseHelper.error_response(f'id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND)
        try:
            serializer = EmployerProfileSerializer(employee, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response('Data updated successfully', serializer.data)
            else:
                return ResponseHelper.error_response('Invalid data', serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while updating data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        responses={
            200: 'Employer profile deleted successfully',
            400: 'id is required in URL to delete data',
            404: 'Employer not found',
            500: 'Internal server error'
        }
    )
    def delete(self, request, id=None):
        """
        Delete an employer profile by ID.
        """
        if not id:
            return ResponseHelper.error_response('id is required in URL to delete data', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            employee = EmployerProfile.objects.get(id=id)
            employee.delete()
            return ResponseHelper.success_response(f'id "{id}" deleted successfully')
        except EmployerProfile.DoesNotExist:
            return ResponseHelper.error_response(f'id "{id}" not found', status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHelper.error_response('Internal server error while deleting data', str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
