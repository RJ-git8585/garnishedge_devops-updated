# app/urls/garnishment_urls.py
from django.urls import path

from processor.views import (
     StateTaxLevyConfigAPIView, StateTaxLevyExemptAmtConfigAPIView,
    StateTaxLevyAppliedRuleAPIView, StateTaxLevyRuleEditPermissionAPIView,
)

app_name = 'garnishment_state'

urlpatterns = [

    # CRUD for the state tax levy config
    path('config-data/',
         StateTaxLevyConfigAPIView.as_view(), name='StateTaxLevyRule'),
    path('config-data/<str:state>/',
         StateTaxLevyConfigAPIView.as_view(), name='StateTaxLevyRule'),

    # CRUD for the state tax levy rule edit request
    path('rule-edit-request/', StateTaxLevyRuleEditPermissionAPIView.as_view(),
         name='StateTaxLevyRuleEditPermissionAPIView'),
    path('rule-edit-request/<str:state>/',
         StateTaxLevyRuleEditPermissionAPIView.as_view(), name='StateTaxLevyRuleEditPermissionAPIView'),

#     # CRUD for the Garnishment fees rules by state
#     path('fees-rules-state/<str:state>/',
#          GarnishmentFeesRulesByState.as_view(), name='fees_rules_state'),
#     path('fees-rules-state/', GarnishmentFeesRulesByState.as_view(),
#          name='fees_rules_state'),

    # CRUD for the state tax levy rule
    path('applied-rule/<str:case_id>/',
         StateTaxLevyAppliedRuleAPIView.as_view(), name='StateTaxLevyRuleAPIView'),

    # CRUD for the state tax levy exempt amt config
    path('exempt-amt-config/', StateTaxLevyExemptAmtConfigAPIView.as_view(),
         name='StateTaxLevyRuleEditPermissionAPIView'),
    path('exempt-amt-config/<str:state>/',
         StateTaxLevyExemptAmtConfigAPIView.as_view(), name='StateTaxLevyRuleEditPermissionAPIView'),
    path('exempt-amt-config/<str:state>/<str:pay_period>/',
         StateTaxLevyExemptAmtConfigAPIView.as_view(), name='StateTaxLevyRuleEditPermissionAPIView'),


]
