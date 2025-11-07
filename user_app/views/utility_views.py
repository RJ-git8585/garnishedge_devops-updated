from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.db.models import Count, Q
from rest_framework.views import APIView
from datetime import datetime, date
from ..models import IWODetailsPDF, GarnishmentOrder, EmployeeDetail
from processor.models import GarnishmentType


class GarnishmentDashboardAPI(APIView):
    """
    API endpoint for garnishment dashboard with KPI calculations and filtering.
    
    Query Parameters:
    - garnishment_type: Filter by garnishment type name (e.g., 'Child Support', 'Tax Levy')
    - client_name: Filter by client name or client_id (accepts both)
    - start_date: Filter orders created from this date (YYYY-MM-DD)
    - end_date: Filter orders created until this date (YYYY-MM-DD)
    """
    
    def get(self, request):
        try:
            # Get filter parameters from query params
            garnishment_type_name = request.GET.get('garnishment_type')
            client_identifier = request.GET.get('client_name')
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            
            # Build base queryset for GarnishmentOrder
            orders_queryset = GarnishmentOrder.objects.select_related(
                'employee', 'garnishment_type', 'employee__client'
            ).all()
            
            # Apply filters
            if garnishment_type_name:
                # Filter by garnishment type name (case-insensitive)
                orders_queryset = orders_queryset.filter(
                    garnishment_type__type__icontains=garnishment_type_name
                )
            
            if client_identifier:
                # Try to filter by client_id first, then by client name
                try:
                    # Check if it's a numeric client_id
                    client_id_int = int(client_identifier)
                    orders_queryset = orders_queryset.filter(
                        employee__client_id=client_id_int
                    )
                except ValueError:
                    # If not numeric, treat as client name (case-insensitive)
                    orders_queryset = orders_queryset.filter(
                        employee__client__legal_name__icontains=client_identifier
                    )
            
            if start_date_str:
                try:
                    start_date = parse_date(start_date_str)
                    if start_date:
                        orders_queryset = orders_queryset.filter(
                            created_at__date__gte=start_date
                        )
                except ValueError:
                    return JsonResponse({
                        'error': 'Invalid start_date format. Use YYYY-MM-DD',
                        'status_code': status.HTTP_400_BAD_REQUEST
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            if end_date_str:
                try:
                    end_date = parse_date(end_date_str)
                    if end_date:
                        orders_queryset = orders_queryset.filter(
                            created_at__date__lte=end_date
                        )
                except ValueError:
                    return JsonResponse({
                        'error': 'Invalid end_date format. Use YYYY-MM-DD',
                        'status_code': status.HTTP_400_BAD_REQUEST
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate KPIs
            
            # 1. Total Active Garnishment
            # Active orders: have start_date and no stop_date (or stop_date is in the future)
            today = date.today()
            active_orders_queryset = orders_queryset.filter(
                Q(start_date__isnull=False) &
                (Q(stop_date__isnull=True) | Q(stop_date__gt=today))
            )
            total_active_garnishment = active_orders_queryset.count()
            
            # 2. Total Garnished Employees
            # Count distinct employees who have garnishment orders
            total_garnished_employees = orders_queryset.values(
                'employee_id'
            ).distinct().count()
            
            # 3. Average Orders Per Employee
            # Calculate average only if there are garnished employees
            average_orders_per_employee = 0
            if total_garnished_employees > 0:
                average_orders_per_employee = round(
                    total_active_garnishment / total_garnished_employees, 2
                )
            
            # 4. Garnishment Type Breakdown
            # Get percentage breakdown of active orders by garnishment type
            garnishment_type_breakdown = []
            if total_active_garnishment > 0:
                type_counts = active_orders_queryset.values(
                    'garnishment_type__type'
                ).annotate(
                    count=Count('id')
                ).order_by('-count')
                
                for type_data in type_counts:
                    percentage = round(
                        (type_data['count'] / total_active_garnishment) * 100, 2
                    )
                    garnishment_type_breakdown.append({
                        'garnishment_type': type_data['garnishment_type__type'],
                        'count': type_data['count'],
                        'percentage': percentage
                    })
            
            # Prepare response data
            dashboard_data = {
                'total_active_garnishment': total_active_garnishment,
                'total_garnished_employees': total_garnished_employees,
                'average_orders_per_employee': average_orders_per_employee,
                'garnishment_type_breakdown': garnishment_type_breakdown,
                'filters_applied': {
                    'garnishment_type': garnishment_type_name,
                    'client_name': client_identifier,
                    'start_date': start_date_str,
                    'end_date': end_date_str
                }
            }
            
            return JsonResponse({
                'success': True,
                'message': 'Dashboard data retrieved successfully',
                'status_code': status.HTTP_200_OK,
                'data': dashboard_data
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error retrieving dashboard data: {str(e)}',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


