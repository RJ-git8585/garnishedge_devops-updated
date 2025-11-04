import os
from pathlib import Path
import dj_database_url
from datetime import timedelta
import environ

# Load environment variables from .env file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SIMPLE_JWT = {
    'USER_ID_FIELD': 'id',
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=10),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

AUTH_USER_MODEL = 'user_app.EmployerProfile'


SECRET_KEY = env('DJANGO_SECRET_KEY')


DEBUG = True
STATIC_URL = '/static/'
ALLOWED_HOSTS = ['*']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'drf_yasg',
    "debug_toolbar",
    "drf_spectacular",
    "drf_spectacular_sidecar", 
    'rest_framework.authtoken',
    'django_rest_passwordreset',
    'rest_framework_simplejwt.token_blacklist',
    'processor',
    'user_app'
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend'
]
INTERNAL_IPS = ['127.0.0.1',]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # User context middleware for model audit logging
    'garnishedge_project.user_context_middleware.UserContextMiddleware',
    # OpenTelemetry audit logging middleware
    'garnishedge_project.audit_middleware.AuditLoggingMiddleware',
    'garnishedge_project.audit_middleware.DatabaseAuditMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware"
]


ROOT_URLCONF = 'garnishedge_project.urls'

# CORS settings
CORS_ALLOWED_ORIGINS = [   
     "http://localhost:5173",
    "https://garnishment-backend.onrender.com"
]


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]



# Django-Celery-Results
CELERY_RESULT_BACKEND = 'django-db'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',

    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    
    
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v2',
    'ALLOWED_VERSIONS': ('v1', 'v2','v3','v4','v5'),
        
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_THROTTLE_RATES': { 'anon': '100/min', 'user': '1000/min' }, 

}

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL')
    )
}


# DATABASES = {
#     'default': {
#         'ENGINE': 'mssql',
#         'NAME': env('AZURE_DB_NAME'),
#         'USER': env('AZURE_DB_USER'),
#         'PASSWORD': env('AZURE_DB_PASSWORD'),
#         'HOST': env('AZURE_DB_HOST'),
#         'PORT': env('AZURE_DB_PORT'),
#         'OPTIONS': {
#             'driver': env('AZURE_DB_DRIVER'),
#             'Encrypt': 'yes',
#             'TrustServerCertificate': 'no',
#         }
#     }
# }

FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_L10N = True

USE_TZ = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


WSGI_APPLICATION = 'garnishedge_project.wsgi.app'


EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

DRF_API_LOGGER_DATABASE = True
DRF_API_LOGGER_STATUS_CODES = {400, 401, 403,
                               404, 500}  # Log only failed req

# OpenTelemetry Configuration
OTEL_SERVICE_NAME = "garnishedge-api"
OTEL_SERVICE_VERSION = "1.0.0"
OTEL_RESOURCE_ATTRIBUTES = f"service.name={OTEL_SERVICE_NAME},service.version={OTEL_SERVICE_VERSION}"

# OpenTelemetry Exporters Configuration
OTLP_ENDPOINT = env('OTLP_ENDPOINT', default='http://localhost:4317')
JAEGER_ENDPOINT = env('JAEGER_ENDPOINT', default='http://localhost:14268/api/traces')
JAEGER_AGENT_HOST = env('JAEGER_AGENT_HOST', default='localhost')
JAEGER_AGENT_PORT = env.int('JAEGER_AGENT_PORT', default=6831)

# Disable OpenTelemetry if collector is not available
OTEL_ENABLED = env.bool('OTEL_ENABLED', default=False)

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

# Check if we're in production (Render deployment)
IS_PRODUCTION = os.getenv('RENDER', False) or os.getenv('DJANGO_ENV') == 'production'

# Logging Configuration for OpenTelemetry
if IS_PRODUCTION:
    # Production logging - use console only for cloud deployment
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'json': {
                'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': True,
            },
            'garnishedge_project.audit_middleware': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'garnishedge_project.audit_logger': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'model_audit': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'opentelemetry': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
else:
    # Development logging - use both console and files
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
            'json': {
                'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': os.path.join(LOGS_DIR, 'audit.log'),
                'formatter': 'json',
            },
            'audit_file': {
                'class': 'logging.FileHandler',
                'filename': os.path.join(LOGS_DIR, 'api_audit.log'),
                'formatter': 'json',
            },
            'model_audit_file': {
                'class': 'logging.FileHandler',
                'filename': os.path.join(LOGS_DIR, 'model_audit.log'),
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
            'garnishedge_project.audit_middleware': {
                'handlers': ['audit_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'garnishedge_project.audit_logger': {
                'handlers': ['audit_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'model_audit': {
                'handlers': ['model_audit_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'opentelemetry': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
