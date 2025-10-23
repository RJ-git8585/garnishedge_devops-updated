import os
from django.core.wsgi import get_wsgi_application

# Initialize OpenTelemetry before Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'garnishedge_project.settings')

# Configure OpenTelemetry
try:
    from garnishedge_project.otel_config import configure_opentelemetry
    configure_opentelemetry()
    print("OpenTelemetry configured successfully")
except Exception as e:
    print(f"Failed to configure OpenTelemetry: {e}")

# Import model signals for audit logging
try:
    import garnishedge_project.model_signals
    print("Model audit signals loaded successfully")
except Exception as e:
    print(f"Failed to load model signals: {e}")

application = get_wsgi_application()
app = application
