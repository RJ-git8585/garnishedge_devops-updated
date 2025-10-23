"""
Custom audit logger utility for detailed API and business logic logging
"""
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from .otel_config import get_tracer, add_audit_event, set_span_status

logger = logging.getLogger(__name__)
User = get_user_model()

class AuditLogger:
    """
    Comprehensive audit logger for API calls and business operations
    """
    
    def __init__(self):
        self.tracer = get_tracer()
    
    def log_api_call(self, request, response=None, exception=None):
        """
        Log comprehensive API call information
        """
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        
        # Basic API call information
        api_info = {
            "method": request.method,
            "path": request.path,
            "full_url": request.build_absolute_uri(),
            "timestamp": datetime.now().isoformat(),
            "user_agent": request.META.get('HTTP_USER_AGENT', ''),
            "client_ip": self._get_client_ip(request),
        }
        
        # Add user information
        if hasattr(request, 'user') and request.user.is_authenticated:
            api_info.update({
                "user_id": str(request.user.id),
                "username": request.user.username,
                "is_staff": request.user.is_staff,
                "is_superuser": request.user.is_superuser,
            })
        
        # Add request data
        if request.method in ['POST', 'PUT', 'PATCH']:
            api_info["request_data"] = self._get_request_data(request)
        
        # Add response information
        if response:
            api_info.update({
                "status_code": response.status_code,
                "response_size": len(response.content) if hasattr(response, 'content') else 0,
            })
        
        # Add exception information
        if exception:
            api_info.update({
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "has_exception": True,
            })
        
        # Add to span attributes
        for key, value in api_info.items():
            span.set_attribute(f"api.{key}", value)
        
        # Add audit event
        add_audit_event(span, "api.call", api_info)
    
    def log_business_operation(self, operation_name: str, details: Dict[str, Any], 
                             user=None, success: bool = True, error_message: str = None):
        """
        Log business operations for audit trail
        """
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        
        operation_info = {
            "operation": operation_name,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "details": details,
        }
        
        if user:
            operation_info.update({
                "user_id": str(user.id),
                "username": user.username,
            })
        
        if error_message:
            operation_info["error_message"] = error_message
        
        # Add to span attributes
        span.set_attribute("business.operation", operation_name)
        span.set_attribute("business.success", success)
        if user:
            span.set_attribute("business.user_id", str(user.id))
        
        # Add audit event
        add_audit_event(span, "business.operation", operation_info)
        
        # Set span status
        if not success:
            set_span_status(span, success=False, error_message=error_message)
    
    def log_data_access(self, model_name: str, operation: str, record_id: str = None,
                       user=None, details: Dict[str, Any] = None):
        """
        Log data access operations for audit trail
        """
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        
        access_info = {
            "model": model_name,
            "operation": operation,  # CREATE, READ, UPDATE, DELETE
            "timestamp": datetime.now().isoformat(),
        }
        
        if record_id:
            access_info["record_id"] = record_id
        
        if user:
            access_info.update({
                "user_id": str(user.id),
                "username": user.username,
            })
        
        if details:
            access_info["details"] = details
        
        # Add to span attributes
        span.set_attribute("data.model", model_name)
        span.set_attribute("data.operation", operation)
        if record_id:
            span.set_attribute("data.record_id", record_id)
        if user:
            span.set_attribute("data.user_id", str(user.id))
        
        # Add audit event
        add_audit_event(span, "data.access", access_info)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          user=None, severity: str = "INFO"):
        """
        Log security-related events
        """
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        
        security_info = {
            "event_type": event_type,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        
        if user:
            security_info.update({
                "user_id": str(user.id),
                "username": user.username,
            })
        
        # Add to span attributes
        span.set_attribute("security.event_type", event_type)
        span.set_attribute("security.severity", severity)
        if user:
            span.set_attribute("security.user_id", str(user.id))
        
        # Add audit event
        add_audit_event(span, "security.event", security_info)
        
        # Log to application logger as well
        if severity == "CRITICAL":
            logger.critical(f"Security event: {event_type} - {details}")
        elif severity == "ERROR":
            logger.error(f"Security event: {event_type} - {details}")
        elif severity == "WARNING":
            logger.warning(f"Security event: {event_type} - {details}")
        else:
            logger.info(f"Security event: {event_type} - {details}")
    
    def log_performance_metric(self, metric_name: str, value: float, 
                              unit: str = "ms", details: Dict[str, Any] = None):
        """
        Log performance metrics
        """
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        
        metric_info = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "timestamp": datetime.now().isoformat(),
        }
        
        if details:
            metric_info["details"] = details
        
        # Add to span attributes
        span.set_attribute(f"performance.{metric_name}", value)
        span.set_attribute(f"performance.{metric_name}.unit", unit)
        
        # Add audit event
        add_audit_event(span, "performance.metric", metric_info)
    
    def _get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_request_data(self, request):
        """Extract request data safely"""
        try:
            if hasattr(request, 'body') and request.body:
                data = request.body.decode('utf-8', errors='ignore')
                # Try to parse as JSON
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    # Return as string if not JSON
                    return data[:1000]  # Limit size
            return None
        except Exception:
            return None

# Global audit logger instance
audit_logger = AuditLogger()

# Convenience functions
def log_api_call(request, response=None, exception=None):
    """Log API call using global audit logger"""
    audit_logger.log_api_call(request, response, exception)

def log_business_operation(operation_name: str, details: Dict[str, Any], 
                         user=None, success: bool = True, error_message: str = None):
    """Log business operation using global audit logger"""
    audit_logger.log_business_operation(operation_name, details, user, success, error_message)

def log_data_access(model_name: str, operation: str, record_id: str = None,
                   user=None, details: Dict[str, Any] = None):
    """Log data access using global audit logger"""
    audit_logger.log_data_access(model_name, operation, record_id, user, details)

def log_security_event(event_type: str, details: Dict[str, Any], 
                      user=None, severity: str = "INFO"):
    """Log security event using global audit logger"""
    audit_logger.log_security_event(event_type, details, user, severity)

def log_performance_metric(metric_name: str, value: float, 
                          unit: str = "ms", details: Dict[str, Any] = None):
    """Log performance metric using global audit logger"""
    audit_logger.log_performance_metric(metric_name, value, unit, details)


