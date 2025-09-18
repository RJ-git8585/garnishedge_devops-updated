from django.urls import path
from processor.views.garnishment_types.creditor_debt_views import (
    CreditorDebtEditPermissionAPIView, CreditorDebtRuleAPIView,  CreditorDebtAppliedRuleAPIView, CreditorDebtExemptAmtConfigAPIView
)

app_name = 'garnishment_creditor'

urlpatterns = [

    # API for returning the rule of creditor debt based on case id
    path('applied-rule/<str:case_id>/',
         CreditorDebtAppliedRuleAPIView.as_view(), name='rule'),

    # CRUD for the Creditor debt exempt amt config
    path('exempt-amt-config/', CreditorDebtExemptAmtConfigAPIView.as_view(),
         name='exempt-amt-config'),
    path('exempt-amt-config/<str:state>/<str:pay_period>/',
         CreditorDebtExemptAmtConfigAPIView.as_view(), name='exempt-amt-config'),
    path('exempt-amt-config/<str:state>/',
         CreditorDebtExemptAmtConfigAPIView.as_view(), name='exempt-amt-config'),

    # CRUD for the creditor debt rule
    path('rule/', CreditorDebtRuleAPIView.as_view(), name='creditor_debt_rule'),
    path('rule/<int:pk>/', CreditorDebtRuleAPIView.as_view(), name='creditor_debt_rule_by_pk'),
    path('rule/<str:state>/', CreditorDebtRuleAPIView.as_view(), name='creditor_debt_rule_by_state'),

    # This is for the state tax levy rule edit request
    path('rule-edit-request/', CreditorDebtEditPermissionAPIView.as_view(),
         name='StateTaxLevyRuleEditPermissionAPIView'),
    path('rule-edit-request/<str:state>/',
         CreditorDebtEditPermissionAPIView.as_view(), name='StateTaxLevyRuleEditPermissionAPIView'),


]
