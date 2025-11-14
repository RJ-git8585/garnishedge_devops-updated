from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.generic import TemplateView
from debug_toolbar.toolbar import debug_toolbar_urls
from drf_yasg import openapi
from rest_framework import permissions
from drf_yasg.views import get_schema_view

schema_view = get_schema_view(
    openapi.Info(
        title="GarnishEdge API",
        default_version="v1",   
        description="This API provides garnishment calculations and related endpoints.",
        terms_of_service="https://garnishedge.com/terms/", 
        contact=openapi.Contact(email="support@garnishedge.com"),  
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

     # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    
    # Swagger UI
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    
    # ReDoc UI
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


    path('APIWebDoc', TemplateView.as_view(
        template_name='doc.html',
        extra_context={'schema_url':'garnishment-schema'}
    ), name='api_doc'),

    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

    # ReDoc UI
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('__debug__/', include('debug_toolbar.urls')),
    path('auth/', include('user_app.urls.auth_urls', namespace='auth')),
    path('employee/', include('user_app.urls.employee_urls', namespace='employee')),
    path('peo/', include('user_app.urls.peo_urls', namespace='peo')),
    path('employer/', include('user_app.urls.employer_urls', namespace='employer')),
    path('client/', include('user_app.urls.client_urls', namespace='client')),
    path('order/', include('user_app.urls.garnishment_order_urls', namespace='garnishment_order')),
    path('payee/', include('user_app.urls.payee_urls', namespace='payee')),
    path('state/', include('processor.urls.garnishment_types.state_urls', namespace='state')),
    path('garnishment/', include('processor.urls.garnishment_types.calculation_urls', namespace='garnishment_calculation')),
    path('garnishment_fees/', include('processor.urls.configs.garnishment_fees_urls', namespace='garnishment_fees')),
    #path('federal_tax/', include('processor.urls.federal_tax_url', namespace='federal_tax')),
    path('child_support/', include('processor.urls.garnishment_types.child_support_urls', namespace='child_support')),
    path('state_tax/', include('processor.urls.garnishment_types.state_tax_urls', namespace='state_tax')), 
    path('iwo_pdf/', include('user_app.urls.iwo_pdf_urls', namespace='garnishment')),
    path('garnishment_state/', include('processor.urls.garnishment_types.state_tax_urls', namespace='garnishment_state')),
    path('garnishment_creditor/', include('processor.urls.garnishment_types.creditor_debt_urls', namespace='garnishment_creditor')),
    path('multiple_garnishment/', include('processor.urls.garnishment_types.multiple_garnishment_urls', namespace='multiple_garnishment')),
    path('dashboard/', include('user_app.urls.utility_urls', namespace='utility')),
    path('exempt_amt/', include('processor.urls.configs.exempt_urls', namespace='exempt_amt')),
    path('exempt/', include('processor.urls.configs.exempt_rule_urls', namespace='exempt_rule')),
    path('letter/', include('user_app.urls.letter_template_urls', namespace='letter_template')),
    path('ach/', include('processor.urls.configs.ach_urls', namespace='ach'))
]

# Serve static files in development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()