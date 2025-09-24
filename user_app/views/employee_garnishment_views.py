from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Prefetch, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from processor.garnishment_library.utils.response import ResponseHelper
from user_app.models import EmployeeDetail, GarnishmentOrder
from user_app.serializers.employee_garnishment_serializers import (
    EmployeeGarnishmentDetailSerializer,
    EmployeeBasicUpdateSerializer,
    GarnishmentDataSerializer
)
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentResultFields as GRF,
    ErrorMessages as EM
)
import logging

logger = logging.getLogger(__name__)


class EmployeeGarnishmentDetailAPI(APIView):
    """
    API for getting employee and garnishment order details based on ee_id and case_id.
    """

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Success', EmployeeGarnishmentDetailSerializer),
            404: 'Employee or case not found',
            500: 'Internal server error'
        }
    )
    def get(self, request, ee_id, case_id):
        """
        Get employee and garnishment order details by ee_id and case_id.
        """
        try:
            # Fetch employee with related garnishment orders
            employee = EmployeeDetail.objects.select_related(
                'home_state', 'work_state', 'filing_status'
            ).prefetch_related(
                Prefetch(
                    'garnishments',
                    queryset=GarnishmentOrder.objects.select_related(
                        'garnishment_type', 'issuing_state'
                    ).order_by('created_at')
                )
            ).get(ee_id__iexact=ee_id)

            # Get the specific garnishment order for the case_id
            garnishment_order = employee.garnishments.filter(case_id=case_id).first()
            if not garnishment_order:
                return ResponseHelper.error_response(
                    message=f"Garnishment order with case_id '{case_id}' not found for employee '{ee_id}'",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Build the complete data structure
            data = self._build_employee_garnishment_data(employee, garnishment_order)
            
            return ResponseHelper.success_response(
                message="Employee and garnishment details fetched successfully",
                data=data,
                status_code=status.HTTP_200_OK
            )

        except EmployeeDetail.DoesNotExist:
            return ResponseHelper.error_response(
                message=f"Employee with ee_id '{ee_id}' not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching employee details for ee_id {ee_id}, case_id {case_id}: {e}")
            return ResponseHelper.error_response(
                message="Failed to fetch employee details",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_employee_garnishment_data(self, employee, garnishment_order):
        """
        Build the complete employee garnishment data structure.
        """
        # Get all garnishment orders for this employee
        all_garnishments = employee.garnishments.all()
        
        # Build garnishment data structure
        garnishment_data = {}
        for garn in all_garnishments:
            garn_type = garn.garnishment_type.type.lower()
            if garn_type not in garnishment_data:
                garnishment_data[garn_type] = []
            
            garnishment_data[garn_type].append({
                "case_id": garn.case_id,
                "ordered_amount": float(garn.ordered_amount),
                "arrear_amount": float(garn.arrear_amount) if garn.arrear_amount else 0.0
            })

        # Convert to list format
        garnishment_data_list = [
            {"type": garn_type, "data": data_list}
            for garn_type, data_list in garnishment_data.items()
        ]

        # Build the complete data structure
        data = {
            "ee_id": employee.ee_id,
            "work_state": employee.work_state.state if employee.work_state else None,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "filing_status": employee.filing_status.name if employee.filing_status else None,
            "no_of_student_default_loan": employee.number_of_student_default_loan,
            "statement_of_exemption_received_date": garnishment_order.received_date.strftime('%m/%d/%Y') if garnishment_order.received_date else "",
            "garn_start_date": garnishment_order.start_date.strftime('%m/%d/%Y') if garnishment_order.start_date else "",
            "support_second_family": employee.support_second_family,
            "arrears_greater_than_12_weeks": garnishment_order.arrear_greater_than_12_weeks,
            "no_of_dependent_child": employee.number_of_dependent_child,
            "consumer_debt": garnishment_order.is_consumer_debt,
            "non_consumer_debt": not garnishment_order.is_consumer_debt,
            "garnishment_data": garnishment_data_list
        }

        return data


class EmployeeGarnishmentUpdateAPI(APIView):
    """
    API for updating employee data based on ee_id and case_id.
    """

    @swagger_auto_schema(
        request_body=EmployeeBasicUpdateSerializer,
        responses={
            200: openapi.Response('Success', EmployeeGarnishmentDetailSerializer),
            404: 'Employee or case not found',
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def put(self, request, ee_id, case_id):
        """
        Update employee data by ee_id and case_id.
        """
        try:
            # Validate input data
            serializer = EmployeeBasicUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return ResponseHelper.error_response(
                    message="Invalid data provided",
                    error=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Get employee
            try:
                employee = EmployeeDetail.objects.select_related(
                    'home_state', 'work_state', 'filing_status'
                ).prefetch_related(
                    Prefetch(
                        'garnishments',
                        queryset=GarnishmentOrder.objects.select_related(
                            'garnishment_type', 'issuing_state'
                        )
                    )
                ).get(ee_id__iexact=ee_id)
            except EmployeeDetail.DoesNotExist:
                return ResponseHelper.error_response(
                    message=f"Employee with ee_id '{ee_id}' not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Verify case_id exists for this employee
            garnishment_order = employee.garnishments.filter(case_id=case_id).first()
            if not garnishment_order:
                return ResponseHelper.error_response(
                    message=f"Garnishment order with case_id '{case_id}' not found for employee '{ee_id}'",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Update employee data
            employee_data = serializer.validated_data
            
            if employee_data:
                for field, value in employee_data.items():
                    setattr(employee, field, value)
                employee.save()

            # Build the complete data structure for response
            data = self._build_employee_garnishment_data(employee, garnishment_order)
            
            return ResponseHelper.success_response(
                message="Employee data updated successfully",
                data=data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error updating employee details for ee_id {ee_id}, case_id {case_id}: {e}")
            return ResponseHelper.error_response(
                message="Failed to update employee details",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_employee_garnishment_data(self, employee, garnishment_order):
        """
        Build the complete employee garnishment data structure.
        """
        # Get all garnishment orders for this employee
        all_garnishments = employee.garnishments.all()
        
        # Build garnishment data structure
        garnishment_data = {}
        for garn in all_garnishments:
            garn_type = garn.garnishment_type.type.lower()
            if garn_type not in garnishment_data:
                garnishment_data[garn_type] = []
            
            garnishment_data[garn_type].append({
                "case_id": garn.case_id,
                "ordered_amount": float(garn.ordered_amount),
                "arrear_amount": float(garn.arrear_amount) if garn.arrear_amount else 0.0
            })

        # Convert to list format
        garnishment_data_list = [
            {"type": garn_type, "data": data_list}
            for garn_type, data_list in garnishment_data.items()
        ]

        # Build the complete data structure
        data = {
            "ee_id": employee.ee_id,
            "work_state": employee.work_state.state if employee.work_state else None,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "filing_status": employee.filing_status.name if employee.filing_status else None,
            "age": getattr(employee, 'age', 0),
            "is_blind": getattr(employee, 'is_blind', 0),
            "is_spouse_blind": getattr(employee, 'is_spouse_blind', 0),
            "spouse_age": getattr(employee, 'spouse_age', 0),
            "no_of_student_default_loan": employee.number_of_student_default_loan,
            "statement_of_exemption_received_date": garnishment_order.received_date.strftime('%m/%d/%Y') if garnishment_order.received_date else "",
            "garn_start_date": garnishment_order.start_date.strftime('%m/%d/%Y') if garnishment_order.start_date else "",
            "support_second_family": employee.support_second_family,
            "arrears_greater_than_12_weeks": garnishment_order.arrear_greater_than_12_weeks,
            "no_of_dependent_child": employee.number_of_dependent_child,
            "consumer_debt": garnishment_order.is_consumer_debt,
            "non_consumer_debt": not garnishment_order.is_consumer_debt,
            "garnishment_data": garnishment_data_list
        }

        return data



class EmployeeGarnishmentListAPI(APIView):
    """
    API for listing all employees with their garnishment orders.
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='page',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                required=False,
                description="Page number for pagination"
            ),
            openapi.Parameter(
                name='page_size',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                required=False,
                description="Number of items per page"
            ),
            openapi.Parameter(
                name='search',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                required=False,
                description="Search term for employee name or ee_id"
            )
        ],
        responses={
            200: openapi.Response('Success', EmployeeGarnishmentDetailSerializer(many=True)),
            500: 'Internal server error'
        }
    )
    def get(self, request):
        """
        Get list of all employees with their garnishment orders.
        """
        try:
            # Get query parameters
            page = request.query_params.get('page', 1)
            page_size = request.query_params.get('page_size', 20)
            search = request.query_params.get('search', '')

            # Build queryset
            queryset = EmployeeDetail.objects.select_related(
                'home_state', 'work_state'
            ).prefetch_related(
                Prefetch(
                    'garnishments',
                    queryset=GarnishmentOrder.objects.select_related(
                        'garnishment_type'
                    ).order_by('created_at')
                )
            ).order_by('-created_at')

            # Apply search filter
            if search:
                queryset = queryset.filter(
                    Q(ee_id__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )

            # Apply pagination
            try:
                page = int(page)
                page_size = int(page_size)
            except (ValueError, TypeError):
                page = 1
                page_size = 20

            start = (page - 1) * page_size
            end = start + page_size

            employees = queryset[start:end]
            total_count = queryset.count()

            # For the list API, we'll return a simplified version of the data
            # since we don't have specific case_id for each employee
            serializer_data = []
            for employee in employees:
                # Get the first garnishment order for each employee
                first_garnishment = employee.garnishments.first()
                if first_garnishment:
                    data = self._build_employee_garnishment_data(employee, first_garnishment)
                    serializer_data.append(data)
                else:
                    # If no garnishment orders, return basic employee data
                    serializer_data.append({
                        "ee_id": employee.ee_id,
                        "work_state": employee.work_state.state if employee.work_state else None,
                        "no_of_exemption_including_self": employee.number_of_exemptions,
                        "filing_status": employee.filing_status.name if employee.filing_status else None,
                        "age": getattr(employee, 'age', 0),
                        "is_blind": getattr(employee, 'is_blind', 0),
                        "is_spouse_blind": getattr(employee, 'is_spouse_blind', 0),
                        "spouse_age": getattr(employee, 'spouse_age', 0),
                        "no_of_student_default_loan": employee.number_of_student_default_loan,
                        "statement_of_exemption_received_date": "",
                        "garn_start_date": "",
                        "support_second_family": employee.support_second_family,
                        "arrears_greater_than_12_weeks": False,
                        "no_of_dependent_child": employee.number_of_dependent_child,
                        "consumer_debt": False,
                        "non_consumer_debt": True,
                        "garnishment_data": []
                    })
            
            response_data = {
                'results': serializer_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }
            
            return ResponseHelper.success_response(
                message="Employees with garnishment details fetched successfully",
                data=response_data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error fetching employees list: {e}")
            return ResponseHelper.error_response(
                message="Failed to fetch employees list",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_employee_garnishment_data(self, employee, garnishment_order):
        """
        Build the complete employee garnishment data structure.
        """
        # Get all garnishment orders for this employee
        all_garnishments = employee.garnishments.all()
        
        # Build garnishment data structure
        garnishment_data = {}
        for garn in all_garnishments:
            garn_type = garn.garnishment_type.type.lower()
            if garn_type not in garnishment_data:
                garnishment_data[garn_type] = []
            
            garnishment_data[garn_type].append({
                "case_id": garn.case_id,
                "ordered_amount": float(garn.ordered_amount),
                "arrear_amount": float(garn.arrear_amount) if garn.arrear_amount else 0.0
            })

        # Convert to list format
        garnishment_data_list = [
            {"type": garn_type, "data": data_list}
            for garn_type, data_list in garnishment_data.items()
        ]

        # Build the complete data structure
        data = {
            "ee_id": employee.ee_id,
            "work_state": employee.work_state.state if employee.work_state else None,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "filing_status": employee.filing_status.name if employee.filing_status else None,
            "age": getattr(employee, 'age', 0),
            "is_blind": getattr(employee, 'is_blind', 0),
            "is_spouse_blind": getattr(employee, 'is_spouse_blind', 0),
            "spouse_age": getattr(employee, 'spouse_age', 0),
            "no_of_student_default_loan": employee.number_of_student_default_loan,
            "statement_of_exemption_received_date": garnishment_order.received_date.strftime('%m/%d/%Y') if garnishment_order.received_date else "",
            "garn_start_date": garnishment_order.start_date.strftime('%m/%d/%Y') if garnishment_order.start_date else "",
            "support_second_family": employee.support_second_family,
            "arrears_greater_than_12_weeks": garnishment_order.arrear_greater_than_12_weeks,
            "no_of_dependent_child": employee.number_of_dependent_child,
            "consumer_debt": garnishment_order.is_consumer_debt,
            "non_consumer_debt": not garnishment_order.is_consumer_debt,
            "garnishment_data": garnishment_data_list
        }

        return data
