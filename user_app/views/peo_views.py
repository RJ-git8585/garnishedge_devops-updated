from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from user_app.models import PEO
from user_app.serializers import PEOSerializer
from processor.garnishment_library.utils import PaginationHelper ,ResponseHelper  


class PEOAPI(APIView):
    """
    API view for listing and creating PEOs.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", PEOSerializer(many=True)),
            500: "Internal Server Error",
        }
    )
    def get(self, request):
        """
        Get paginated list of active PEOs with optional filters:
        - ?state_code=CA
        - ?peo_id=PEO123
        """
        try:
            queryset = PEO.objects.filter(is_active=True).order_by("-created_at")

            state_code = request.query_params.get("state_code")
            peo_id = request.query_params.get("peo_id")

            if state_code:
                queryset = queryset.filter(state__state_code=state_code)
            if peo_id:
                queryset = queryset.filter(peo_id=peo_id)

            result = PaginationHelper.paginate_queryset(queryset, request, PEOSerializer)
            return ResponseHelper.success_response(
                message="PEOs fetched successfully",
                data=result,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to fetch PEOs",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=PEOSerializer,
        responses={
            201: openapi.Response("Created", PEOSerializer),
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        """
        Create a new PEO.
        """
        serializer = PEOSerializer(data=request.data)
        if serializer.is_valid():
            try:
                peo = serializer.save()
                return ResponseHelper.success_response(
                    message="PEO created successfully",
                    data=PEOSerializer(peo).data,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to create PEO",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while creating PEO",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PEOByIdAPI(APIView):
    """
    API view for retrieving, updating, or deleting a specific PEO by ID.
    """

    def get_object(self, pk):
        try:
            return PEO.objects.get(pk=pk, is_active=True)
        except PEO.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Success", PEOSerializer),
            404: "Not Found",
        }
    )
    def get(self, request, pk):
        """
        Retrieve details of a specific PEO.
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        return ResponseHelper.success_response(
            message="PEO fetched successfully",
            data=PEOSerializer(peo).data,
            status_code=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        request_body=PEOSerializer,
        responses={
            200: openapi.Response("Updated", PEOSerializer),
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, pk):
        """
        Update an existing PEO (partial updates supported).
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = PEOSerializer(peo, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                peo = serializer.save()
                return ResponseHelper.success_response(
                    message="PEO updated successfully",
                    data=PEOSerializer(peo).data,
                    status_code=status.HTTP_200_OK
                )
            except Exception as e:
                return ResponseHelper.error_response(
                    message="Failed to update PEO",
                    error=str(e),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return ResponseHelper.error_response(
            message="Validation error while updating PEO",
            error=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    @swagger_auto_schema(
        responses={
            204: "Deleted",
            404: "Not Found",
            500: "Internal Server Error",
        }
    )
    def delete(self, request, pk):
        """
        Soft delete a PEO (mark as inactive).
        """
        peo = self.get_object(pk)
        if not peo:
            return ResponseHelper.error_response(
                message="PEO not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            peo.is_active = False
            peo.save(update_fields=["is_active"])
            return ResponseHelper.success_response(
                message="PEO deleted successfully",
                data={},
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message="Failed to delete PEO",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
