"""
Simplified OpenTelemetry configuration for audit logging
OpenTelemetry is disabled by default - audit logging uses files only
"""
import os
import logging
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Simple fallback constants
class SpanAttributes:
    HTTP_METHOD = "http.method"
    HTTP_URL = "http.url"
    HTTP_SCHEME = "http.scheme"
    HTTP_HOST = "http.host"
    HTTP_TARGET = "http.target"
    HTTP_USER_AGENT = "http.user_agent"
    HTTP_REQUEST_CONTENT_LENGTH = "http.request_content_length"
    HTTP_STATUS_CODE = "http.status_code"

# Simple configuration - OpenTelemetry is disabled by default
OTEL_ENABLED = os.getenv('OTEL_ENABLED', 'False').lower() == 'true'

logger = logging.getLogger(__name__)

def configure_opentelemetry():
    """
    Configure OpenTelemetry for the application (simplified)
    """
    if not OTEL_ENABLED:
        logger.info("OpenTelemetry is disabled - using file-based audit logging only")
        return
    
    logger.info("OpenTelemetry is enabled but no external services configured")

def get_tracer():
    """
    Get the OpenTelemetry tracer (disabled)
    """
    return None

def create_audit_span(name: str, attributes: dict = None):
    """
    Create a new span for audit logging (disabled)
    """
    return None

def add_audit_event(span, event_name: str, attributes: dict = None):
    """
    Add an event to a span (disabled)
    """
    pass

def set_span_status(span, success: bool = True, error_message: str = None):
    """
    Set the status of a span (disabled)
    """
    pass

def end_span(span):
    """
    End a span (disabled)
    """
    pass