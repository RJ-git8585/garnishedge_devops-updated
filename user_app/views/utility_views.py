from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import IWODetailsPDF
from django.db.models import Count
from rest_framework.views import APIView


@csrf_exempt
def get_dashboard_data(request):
    try:
        total_iwo = IWODetailsPDF.objects.count()

        employees_with_single_iwo = IWODetailsPDF.objects.values(
            'cid').annotate(iwo_count=Count('cid')).filter(iwo_count=1).count()

        employees_with_multiple_iwo = IWODetailsPDF.objects.values(
            'cid').annotate(iwo_count=Count('cid')).filter(iwo_count__gt=1).count()

        active_employees = IWODetailsPDF.objects.filter(
            IWO_Status='active').count()

        data = {
            'Total_IWO': total_iwo,
            'Employees_with_Single_IWO': employees_with_single_iwo,
            'Employees_with_Multiple_IWO': employees_with_multiple_iwo,
            'Active_employees': active_employees,
        }
    except Exception as e:
        return JsonResponse({'error': str(e), "status code": status.HTTP_500_INTERNAL_SERVER_ERROR})
    response_data = {
        'success': True,
        'message': 'Data Get Successfully',
        'status code': status.HTTP_200_OK,
        'data': data}
    return JsonResponse(response_data)


