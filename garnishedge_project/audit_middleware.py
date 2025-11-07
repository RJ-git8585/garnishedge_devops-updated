"""
Custom middleware for comprehensive API audit logging using OpenTelemetry
"""
import json
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from .otel_config import get_tracer, add_audit_event, set_span_status
from .user_context_middleware import set_current_user
from .model_audit import AuditJSONEncoder
try:
    from opentelemetry.semantic_conventions.trace import SpanAttributes
except ImportError:
    try:
        from opentelemetry.semantic_conventions import SpanAttributes
    except ImportError:
        # Define fallback constants
        class SpanAttributes:
            HTTP_METHOD = "http.method"
            HTTP_URL = "http.url"
            HTTP_SCHEME = "http.scheme"
            HTTP_HOST = "http.host"
            HTTP_TARGET = "http.target"
            HTTP_USER_AGENT = "http.user_agent"
            HTTP_REQUEST_CONTENT_LENGTH = "http.request_content_length"
            HTTP_STATUS_CODE = "http.status_code"


logger = logging.getLogger(__name__)
User = get_user_model()

class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all API calls with comprehensive audit information
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process incoming request and start audit logging"""
        # Start timing
        request._audit_start_time = time.time()
        
        # Get tracer and create span (only if OpenTelemetry is enabled)
        tracer = get_tracer()
        span = None
        if tracer:
            span_name = f"{request.method} {request.path}"
            span = tracer.start_span(span_name)
        
        # Set basic span attributes (only if span exists)
        if span:
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
            span.set_attribute(SpanAttributes.HTTP_URL, request.build_absolute_uri())
            span.set_attribute(SpanAttributes.HTTP_SCHEME, request.scheme)
            span.set_attribute(SpanAttributes.HTTP_HOST, request.get_host())
            span.set_attribute(SpanAttributes.HTTP_TARGET, request.path)
            span.set_attribute(SpanAttributes.HTTP_USER_AGENT, request.META.get('HTTP_USER_AGENT', ''))
            span.set_attribute(SpanAttributes.HTTP_REQUEST_CONTENT_LENGTH, 
                              request.META.get('CONTENT_LENGTH', 0))
            
            # Add client IP information
            client_ip = self._get_client_ip(request)
            span.set_attribute("client.ip", client_ip)
            
            # Add request headers (filter sensitive ones) - limit size
            headers = self._filter_sensitive_headers(dict(request.headers))
            headers_json = json.dumps(headers, cls=AuditJSONEncoder)
            if len(headers_json) < 2000:  # Limit headers size
                span.set_attribute("http.request.headers", headers_json)
            else:
                span.set_attribute("http.request.headers_count", len(headers))
                span.set_attribute("http.request.headers_truncated", True)
            
            # Add query parameters
            if request.GET:
                span.set_attribute("http.request.query_params", json.dumps(dict(request.GET), cls=AuditJSONEncoder))
            
            # Add request body for non-GET requests (with size limit)
            if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
                body = request.body.decode('utf-8', errors='ignore')
                if len(body) < 2000:  # Reduced limit to prevent large payloads
                    span.set_attribute("http.request.body", body)
                else:
                    span.set_attribute("http.request.body_size", len(body))
                    span.set_attribute("http.request.body_truncated", True)
            
            # Add user information if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                span.set_attribute("user.id", str(request.user.id))
                span.set_attribute("user.username", request.user.username)
                if hasattr(request.user, 'email'):
                    span.set_attribute("user.email", request.user.email)
            
            # Add session information
            if hasattr(request, 'session') and request.session.session_key:
                span.set_attribute("session.id", request.session.session_key)
            
            # Add audit event for request start
            add_audit_event(span, "request.started", {
                "timestamp": time.time(),
                "request_id": getattr(request, 'id', None)
            })
        
        # Set current user for model signals (always do this)
        if hasattr(request, 'user') and request.user.is_authenticated:
            set_current_user(request.user)
        
        # Store span in request for later use
        request._audit_span = span
        
        # Log to file only - removed console output
    
    def process_response(self, request, response):
        """Process outgoing response and complete audit logging"""
        if not hasattr(request, '_audit_span'):
            return response
        
        span = request._audit_span
        start_time = getattr(request, '_audit_start_time', time.time())
        duration = time.time() - start_time
        
        # Only process span if it exists (OpenTelemetry enabled)
        if span:
            # Set response attributes
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
            span.set_attribute("http.response.duration_ms", round(duration * 1000, 2))
            
            # Add response headers (filter sensitive ones) - limit size
            if hasattr(response, 'headers'):
                headers = self._filter_sensitive_headers(dict(response.headers))
                headers_json = json.dumps(headers, cls=AuditJSONEncoder)
                if len(headers_json) < 1000:  # Limit response headers size
                    span.set_attribute("http.response.headers", headers_json)
                else:
                    span.set_attribute("http.response.headers_count", len(headers))
                    span.set_attribute("http.response.headers_truncated", True)
            
            # Add response body for error responses (with size limit)
            if response.status_code >= 400 and hasattr(response, 'content'):
                content = response.content.decode('utf-8', errors='ignore')
                if len(content) < 1000:  # Reduced limit to prevent large payloads
                    span.set_attribute("http.response.body", content)
                else:
                    span.set_attribute("http.response.body_size", len(content))
                    span.set_attribute("http.response.body_truncated", True)
            
            # Set span status based on response
            if response.status_code >= 400:
                set_span_status(span, success=False, 
                              error_message=f"HTTP {response.status_code}")
            else:
                set_span_status(span, success=True)
            
            # Add audit event for request completion
            add_audit_event(span, "request.completed", {
                "timestamp": time.time(),
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            })
            
            # End the span
            span.end()
        
        return response
    
    def process_exception(self, request, exception):
        """Process exceptions and log them in audit trail"""
        if not hasattr(request, '_audit_span'):
            return None
        
        span = request._audit_span
        
        # Only process span if it exists (OpenTelemetry enabled)
        if span:
            # Set exception attributes
            span.set_attribute("exception.type", type(exception).__name__)
            span.set_attribute("exception.message", str(exception))
            span.set_attribute("exception.stacktrace", self._get_exception_traceback(exception))
            
            # Set span status to error
            set_span_status(span, success=False, error_message=str(exception))
            
            # Add audit event for exception
            add_audit_event(span, "request.exception", {
                "timestamp": time.time(),
                "exception_type": type(exception).__name__,
                "exception_message": str(exception)
            })
            
            # End the span
            span.end()
        
        logger.error(f"API Request failed: {request.method} {request.path} - "
                    f"{type(exception).__name__}: {str(exception)}")
        
        return None
    
    def _get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _filter_sensitive_headers(self, headers):
        """Filter out sensitive headers from logging"""
        sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token',
            'x-csrf-token', 'x-session-id', 'x-access-token'
        }
        
        filtered_headers = {}
        for key, value in headers.items():
            if key.lower() not in sensitive_headers:
                filtered_headers[key] = value
            else:
                filtered_headers[key] = '[REDACTED]'
        
        return filtered_headers
    
    def _get_exception_traceback(self, exception):
        """Get formatted exception traceback"""
        import traceback
        return traceback.format_exc()

class DatabaseAuditMiddleware(MiddlewareMixin):
    """
    Middleware to log database operations for audit purposes
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Initialize database query tracking"""
        from django.db import connection
        request._db_queries_start = len(connection.queries)
        request._db_queries_time_start = time.time()
    
    def process_response(self, request, response):
        """Log database query information"""
        if not hasattr(request, '_db_queries_start'):
            return response
        
        from django.db import connection
        
        queries_executed = len(connection.queries) - request._db_queries_start
        db_time = time.time() - request._db_queries_time_start
        
        # Add database metrics to current span if available
        span = getattr(request, '_audit_span', None)
        if span and span.is_recording():
            span.set_attribute("db.queries.count", queries_executed)
            span.set_attribute("db.queries.duration_ms", round(db_time * 1000, 2))
            
            # Log slow queries
            if db_time > 1.0:  # Queries taking more than 1 second
                add_audit_event(span, "db.slow_query", {
                    "duration_ms": round(db_time * 1000, 2),
                    "query_count": queries_executed
                })
        
        return response
