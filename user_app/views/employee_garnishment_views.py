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
    def get(self, request, ee_id, client_id):
        """
        Get employee and garnishment order details by ee_id and client_id.
        """
        try:
            # Fetch employee with related garnishment orders filtered by ee_id and client_id
            employee = EmployeeDetail.objects.select_related(
                'home_state', 'work_state', 'filing_status', 'client'
            ).prefetch_related(
                Prefetch(
                    'garnishments',
                    queryset=GarnishmentOrder.objects.select_related(
                        'garnishment_type', 'issuing_state'
                    ).order_by('created_at')
                )
            ).get(ee_id__iexact=ee_id, client__client_id__iexact=client_id)

            # Get the first garnishment order for building the data structure
            garnishment_order = employee.garnishments.first()
            if not garnishment_order:
                # If no garnishment orders, still return employee data with empty garnishment_data
                data = self._build_employee_garnishment_data(employee, None)
            else:
                # Build the complete data structure
                data = self._build_employee_garnishment_data(employee, garnishment_order)
            
            return ResponseHelper.success_response(
                message="Employee and garnishment details fetched successfully",
                data=data,
                status_code=status.HTTP_200_OK
            )

        except EmployeeDetail.DoesNotExist:
            return ResponseHelper.error_response(
                message=f"Employee with ee_id '{ee_id}' and client_id '{client_id}' not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching employee details for ee_id {ee_id}, client_id {client_id}: {e}")
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
        is_multiple_garnishment_type = True if len(garnishment_data_list) >1  else False

        # Build the complete data structure
        data = {
            "ee_id": employee.ee_id,
            "home_state": employee.home_state.state if employee.home_state else None,
            "work_state": employee.work_state.state if employee.work_state else None,
            "is_multiple_garnishment_type": is_multiple_garnishment_type,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "filing_status": employee.filing_status.name if employee.filing_status else None,
            "no_of_student_default_loan": employee.number_of_student_default_loan,
            "statement_of_exemption_received_date": garnishment_order.received_date.strftime('%m/%d/%Y') if garnishment_order and garnishment_order.received_date else "",
            "garn_start_date": garnishment_order.start_date.strftime('%m/%d/%Y') if garnishment_order and garnishment_order.start_date else "",
            "support_second_family": employee.support_second_family,
            "arrears_greater_than_12_weeks": garnishment_order.arrear_greater_than_12_weeks if garnishment_order else False,
            "no_of_dependent_child": employee.number_of_dependent_child,
            "consumer_debt": garnishment_order.is_consumer_debt if garnishment_order else False,
            "non_consumer_debt": not garnishment_order.is_consumer_debt if garnishment_order else True,
            "garnishment_data": garnishment_data_list
        }

        return data


class EmployeeGarnishmentUpdateAPI(APIView):
    """
    API for updating employee data based on ee_id and client_id.
    """

    @swagger_auto_schema(
        request_body=EmployeeBasicUpdateSerializer,
        responses={
            200: openapi.Response('Success', EmployeeGarnishmentDetailSerializer),
            404: 'Employee not found',
            400: 'Invalid data',
            500: 'Internal server error'
        }
    )
    def put(self, request, ee_id, client_id):
        """
        Update employee data by ee_id and client_id.
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

            # Get employee filtered by ee_id and client_id
            try:
                employee = EmployeeDetail.objects.select_related(
                    'home_state', 'work_state', 'filing_status', 'client'
                ).prefetch_related(
                    Prefetch(
                        'garnishments',
                        queryset=GarnishmentOrder.objects.select_related(
                            'garnishment_type', 'issuing_state'
                        )
                    )
                ).get(ee_id__iexact=ee_id, client__client_id__iexact=client_id)
            except EmployeeDetail.DoesNotExist:
                return ResponseHelper.error_response(
                    message=f"Employee with ee_id '{ee_id}' and client_id '{client_id}' not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Separate employee and garnishment order fields
            employee_data = {}
            garnishment_data = {}
            
            # Fields that belong to EmployeeDetail model
            employee_fields = {
                'first_name', 'last_name', 'home_state', 'work_state', 'number_of_exemptions',
                'marital_status', 'number_of_student_default_loan', 'number_of_dependent_child',
                'support_second_family', 'garnishment_fees_status', 'number_of_active_garnishment',
                'is_active', 'filing_status'
            }
            
            # Fields that belong to GarnishmentOrder model
            garnishment_fields = {
                'garnishment_type', 'is_consumer_debt', 'received_date', 'start_date',
                'stop_date', 'ordered_amount', 'arrear_amount', 'arrear_greater_than_12_weeks'
            }
            
            # Handle garnishment_data updates (special case)
            garnishment_data_updates = {}
            if 'garnishment_data' in serializer.validated_data:
                garnishment_data_updates = serializer.validated_data.pop('garnishment_data')
            
            # Separate the data
            for field, value in serializer.validated_data.items():
                if field in employee_fields:
                    employee_data[field] = value
                elif field in garnishment_fields:
                    garnishment_data[field] = value
            
            # Update employee and garnishment data in a transaction
            with transaction.atomic():
                # Update employee data
                if employee_data:
                    logger.info(f"Updating employee {ee_id} with data: {employee_data}")
                    for field, value in employee_data.items():
                        setattr(employee, field, value)
                    employee.save()
                    logger.info(f"Employee {ee_id} updated successfully. New values: {employee_data}")
                
                # Update garnishment order data
                if garnishment_data:
                    logger.info(f"Updating garnishment orders for employee {ee_id} with data: {garnishment_data}")
                    # Update all garnishment orders for this employee
                    garnishment_orders = employee.garnishments.all()
                    for garnishment_order in garnishment_orders:
                        for field, value in garnishment_data.items():
                            setattr(garnishment_order, field, value)
                        garnishment_order.save()
                    logger.info(f"Garnishment orders for employee {ee_id} updated successfully. New values: {garnishment_data}")
                
                # Handle garnishment_data updates (update individual garnishment orders)
                if garnishment_data_updates:
                    logger.info(f"Updating garnishment data for employee {ee_id}: {garnishment_data_updates}")
                    garnishment_orders = employee.garnishments.all()
                    
                    for garnishment_data_item in garnishment_data_updates:
                        garnishment_type = garnishment_data_item.get('type')
                        data_list = garnishment_data_item.get('data', [])
                        
                        # Find garnishment orders of this type
                        matching_orders = garnishment_orders.filter(
                            garnishment_type__type__iexact=garnishment_type
                        )

                        
                        # Update each matching order with the data
                        for i, order in enumerate(matching_orders):
                            if i < len(data_list):
                                data_item = data_list[i]
                                if 'case_id' in data_item:
                                    order.case_id = data_item['case_id']
                                if 'ordered_amount' in data_item:
                                    order.ordered_amount = data_item['ordered_amount']
                                if 'arrear_amount' in data_item:
                                    order.arrear_amount = data_item['arrear_amount']
                                order.save()
                    
                    logger.info(f"Garnishment data for employee {ee_id} updated successfully")
                
                if not employee_data and not garnishment_data and not garnishment_data_updates:
                    logger.warning(f"No valid data provided for employee {ee_id} update")


            # Refresh the employee object from database to ensure we have the latest data
            employee.refresh_from_db()
            
            # Get the first garnishment order for building the data structure
            garnishment_order = employee.garnishments.first()
            
            # Build the complete data structure for response
            data = self._build_employee_garnishment_data(employee, garnishment_order)
            
            return ResponseHelper.success_response(
                message="Employee data updated successfully",
                data=data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error updating employee details for ee_id {ee_id}, client_id {client_id}: {e}")
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

        is_multiple_garnishment_type = True if len(garnishment_data_list) > 1 else False

        # Build the complete data structure - matching the GET API structure
        data = {
            "ee_id": employee.ee_id,
            "home_state": employee.home_state.state if employee.home_state else None,
            "work_state": employee.work_state.state if employee.work_state else None,
            "is_multiple_garnishment_type": is_multiple_garnishment_type,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "filing_status": employee.filing_status.name if employee.filing_status else None,
            "no_of_student_default_loan": employee.number_of_student_default_loan,
            "statement_of_exemption_received_date": garnishment_order.received_date.strftime('%m/%d/%Y') if garnishment_order and garnishment_order.received_date else "",
            "garn_start_date": garnishment_order.start_date.strftime('%m/%d/%Y') if garnishment_order and garnishment_order.start_date else "",
            "support_second_family": employee.support_second_family,
            "arrears_greater_than_12_weeks": garnishment_order.arrear_greater_than_12_weeks if garnishment_order else False,
            "no_of_dependent_child": employee.number_of_dependent_child,
            "consumer_debt": garnishment_order.is_consumer_debt if garnishment_order else False,
            "non_consumer_debt": not garnishment_order.is_consumer_debt if garnishment_order else True,
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
                        "home_state": employee.home_state.state if employee.home_state else None,
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

        is_multiple_garnishment_type = True if len(garnishment_data_list) >1  else False
        # Build the complete data structure
        data = {
            "ee_id": employee.ee_id,
            "work_state": employee.work_state.state if employee.work_state else None,
            "no_of_exemption_including_self": employee.number_of_exemptions,
            "is_multiple_garnishment_type": is_multiple_garnishment_type,
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
