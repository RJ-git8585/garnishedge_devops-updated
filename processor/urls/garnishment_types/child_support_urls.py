# app/urls/garnishment_urls.py
from django.urls import path
from processor.views import ChildSupportCalculationRules
from processor.views.garnishment_types.child_support_views import WithholdingRulesAPIView, WithholdingLimitAPIView, DeductionPriorityAPIView, DeductionPriorityReorderAPIView



app_name = 'child_support'

urlpatterns = [

    # Child support calculation rule
    path('rules/<str:state>/<str:employee_id>/<str:supports_2nd_family>/<str:arrears_of_more_than_12_weeks>/<str:de>/<int:no_of_order>/',
         ChildSupportCalculationRules.as_view(), name='calculation_rules'),

    # WithholdingRules CRUD endpoints
    path('withholding-rules/', WithholdingRulesAPIView.as_view(), name='withholding_rules_list_create'),
    path('withholding-rules/<int:pk>/', WithholdingRulesAPIView.as_view(), name='withholding_rules_detail'),

    # WithholdingLimit CRUD endpoints
    path('withholding-limits/', WithholdingLimitAPIView.as_view(), name='withholding_limit_list_create'),
    path('withholding-limits/<int:pk>/', WithholdingLimitAPIView.as_view(), name='withholding_limit_detail'),
    path('withholding-limits/rule/<int:rule_id>/', WithholdingLimitAPIView.as_view(), name='withholding_limit_by_rule'),

    # DeductionPriority CRUD endpoints
    path('deduction-priorities/', DeductionPriorityAPIView.as_view(), name='deduction_priority_list_create'),
    path('deduction-priorities/<int:pk>/', DeductionPriorityAPIView.as_view(), name='deduction_priority_detail'),
    path('deduction-priorities/reorder/', DeductionPriorityReorderAPIView.as_view(), name='deduction_priority_reorder'),

         
]