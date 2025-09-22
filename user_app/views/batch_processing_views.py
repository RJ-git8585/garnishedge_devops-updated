from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Prefetch
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from processor.garnishment_library.utils.response import ResponseHelper

from user_app.models import EmployeeDetail, GarnishmentOrder
from user_app.serializers.batch_processing_serializers import (
    BatchInputSerializer,
    BatchOutputSerializer,
    BatchCaseOutputSerializer,
    EmployeeNotFoundSerializer
)


class BatchPayrollProcessingAPI(APIView):
    """
    API endpoint to process batch payroll data and enrich it with employee and garnishment information.
    """

    @swagger_auto_schema(
        request_body=BatchInputSerializer,
        responses={
            200: openapi.Response('Success', BatchOutputSerializer),
            400: openapi.Response('Bad Request', EmployeeNotFoundSerializer),
            500: 'Internal server error'
        },
        operation_description="Process batch payroll data and enrich with employee/garnishment information"
    )
    def post(self, request):
        """
        Process batch payroll data and enrich each case with employee and garnishment information.
        """
        try:
            # Validate input data
            input_serializer = BatchInputSerializer(data=request.data)
            if not input_serializer.is_valid():
                return ResponseHelper.error_response(
                    message="Invalid input data",
                    error=input_serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            batch_data = input_serializer.validated_data
            batch_id = batch_data['batch_id']
            cases = batch_data['cases']
            
            enriched_cases = []
            not_found_employees = []

            # Process each case
            for case in cases:
                ee_id = case['ee_id']
                
                try:
                    # Fetch employee with related garnishment orders
                    employee = EmployeeDetail.objects.select_related(
                        'home_state', 'work_state', 'filing_status'
                    ).prefetch_related(
                        Prefetch(
                            'garnishments',
                            queryset=GarnishmentOrder.objects.select_related(
                                'issuing_state', 'garnishment_type'
                            )
                        )
                    ).get(ee_id=ee_id)

                    # Build enriched case data
                    enriched_case = self._build_enriched_case(case, employee)
                    enriched_cases.append(enriched_case)

                except EmployeeDetail.DoesNotExist:
                    # Log missing employee and continue processing
                    not_found_employees.append({
                        'not_found': ee_id,
                        'message': f'ee_id {ee_id} is not found in the records'
                    })

            # Prepare response
            if not_found_employees and not enriched_cases:
                # All employees not found
                return ResponseHelper.error_response(
                    message="No employees found",
                    error=not_found_employees[0],
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            elif not_found_employees:
                # Some employees not found, but some were processed
                response_data = {
                    'batch_id': batch_id,
                    'cases': enriched_cases,
                    'not_found_employees': not_found_employees
                }
            else:
                # All employees found and processed
                response_data = {
                    'batch_id': batch_id,
                    'cases': enriched_cases
                }

            return ResponseHelper.success_response(
                message="Batch processing completed",
                data=response_data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            return ResponseHelper.error_response(
                message="Internal server error during batch processing",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_enriched_case(self, case, employee):
        """
        Build enriched case data by merging employee and garnishment information.
        """
        # Get garnishment orders grouped by type
        garnishment_orders = employee.garnishments.all()
        garnishment_data = {}
        garnishment_types = []

        for garnishment in garnishment_orders:
            garn_type = garnishment.garnishment_type.type
            if garn_type not in garnishment_data:
                garnishment_data[garn_type] = []
                garnishment_types.append(garn_type)
            
            garnishment_data[garn_type].append({
                'case_id': garnishment.case_id,
                'ordered_amount': float(garnishment.ordered_amount),
                'arrear_amount': float(garnishment.arrear_amount) if garnishment.arrear_amount else 0.0
            })

        # Build garnishment data structure
        garnishment_data_list = []
        for garn_type in garnishment_types:
            garnishment_data_list.append({
                'type': garn_type,
                'data': garnishment_data[garn_type]
            })

        # Get the first garnishment order for some fields (issuing_state, etc.)
        first_garnishment = garnishment_orders.first() if garnishment_orders.exists() else None

        # Build enriched case
        enriched_case = {
            'ee_id': case['ee_id'],
            'work_state': employee.work_state.state if employee.work_state else None,
            'home_state': employee.home_state.state if employee.home_state else None,
            'issuing_state': first_garnishment.issuing_state.state_code.lower() if first_garnishment and first_garnishment.issuing_state else None,
            'no_of_exemption_including_self': employee.number_of_exemptions,
            'is_multiple_garnishment_type': len(garnishment_types) > 1,
            'no_of_student_default_loan': employee.number_of_student_default_loan,
            'pay_period': case['pay_period'],
            'filing_status': employee.filing_status.name if employee.filing_status else None,
            'wages': float(case['wages']),
            'commission_and_bonus': float(case['commission_and_bonus']),
            'non_accountable_allowances': float(case['non_accountable_allowances']),
            'gross_pay': float(case['gross_pay']),
            'payroll_taxes': case['payroll_taxes'],
            'net_pay': float(case['net_pay']),
            'is_blind': employee.is_blind,
            'statement_of_exemption_received_date': first_garnishment.received_date.strftime('%m-%d-%Y') if first_garnishment and first_garnishment.received_date else None,
            'garn_start_date': first_garnishment.start_date.strftime('%m-%d-%Y') if first_garnishment and first_garnishment.start_date else None,
            'non_consumer_debt': not first_garnishment.is_consumer_debt if first_garnishment else False,
            'consumer_debt': first_garnishment.is_consumer_debt if first_garnishment else False,
            'age': employee.age,
            'spouse_age': employee.spouse_age,
            'is_spouse_blind': employee.is_spouse_blind,
            'support_second_family': employee.support_second_family,
            'no_of_dependent_child': employee.number_of_dependent_child,
            'arrear_greater_than_12_weeks': first_garnishment.arrear_greater_than_12_weeks if first_garnishment else False,
            'ftb_type': None,  # This field doesn't exist in the models, setting to None
            'garnishment_data': garnishment_data_list,
            'garnishment_orders': garnishment_types
        }

        return enriched_case
