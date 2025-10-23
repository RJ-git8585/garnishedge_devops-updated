"""
Decorators for automatic audit logging in Django views
"""
import time
import functools
from typing import Callable, Any
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model
from opentelemetry import trace
from .audit_logger import audit_logger, log_business_operation, log_data_access

User = get_user_model()

def audit_api_call(view_func: Callable) -> Callable:
    """
    Decorator to automatically log API calls with comprehensive audit information
    Works with both function-based and class-based views
    """
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs) -> HttpResponse:
        start_time = time.time()
        
        # Determine if this is a class-based view or function-based view
        # In class-based views, the first arg is 'self' and the second is 'request'
        # In function-based views, the first arg is 'request'
        if len(args) >= 2 and hasattr(args[0], 'request'):
            # This is a class-based view method (self, request, ...)
            request = args[1]
        elif len(args) >= 1 and hasattr(args[0], 'method'):
            # This is a function-based view (request, ...)
            request = args[0]
        else:
            # Fallback: try to find request in kwargs
            request = kwargs.get('request')
            if not request:
                # If we can't find request, just execute the view without logging
                return view_func(*args, **kwargs)
        
        # Log API call start
        audit_logger.log_api_call(request)
        
        try:
            # Execute the view
            response = view_func(*args, **kwargs)
            
            # Log API call completion
            audit_logger.log_api_call(request, response)
            
            return response
            
        except Exception as e:
            # Log API call with exception
            audit_logger.log_api_call(request, exception=e)
            raise
    
    return wrapper

def audit_business_operation(operation_name: str, log_user: bool = True):
    """
    Decorator to log business operations with audit trail
    Works with both function-based and class-based views
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs) -> HttpResponse:
            # Determine if this is a class-based view or function-based view
            if len(args) >= 2 and hasattr(args[0], 'request'):
                # This is a class-based view method (self, request, ...)
                request = args[1]
            elif len(args) >= 1 and hasattr(args[0], 'method'):
                # This is a function-based view (request, ...)
                request = args[0]
            else:
                # Fallback: try to find request in kwargs
                request = kwargs.get('request')
                if not request:
                    # If we can't find request, just execute the view without logging
                    return view_func(*args, **kwargs)
            
            user = request.user if log_user and hasattr(request, 'user') else None
            
            try:
                # Execute the view
                response = view_func(*args, **kwargs)
                
                # Log successful business operation
                log_business_operation(
                    operation_name,
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                    },
                    user=user,
                    success=True
                )
                
                return response
                
            except Exception as e:
                # Log failed business operation
                log_business_operation(
                    operation_name,
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "error": str(e),
                    },
                    user=user,
                    success=False,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator

def audit_data_access(model_name: str, operation: str = "READ"):
    """
    Decorator to log data access operations
    Works with both function-based and class-based views
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs) -> HttpResponse:
            # Determine if this is a class-based view or function-based view
            if len(args) >= 2 and hasattr(args[0], 'request'):
                # This is a class-based view method (self, request, ...)
                request = args[1]
            elif len(args) >= 1 and hasattr(args[0], 'method'):
                # This is a function-based view (request, ...)
                request = args[0]
            else:
                # Fallback: try to find request in kwargs
                request = kwargs.get('request')
                if not request:
                    # If we can't find request, just execute the view without logging
                    return view_func(*args, **kwargs)
            
            user = request.user if hasattr(request, 'user') else None
            
            # Extract record ID from kwargs if available
            record_id = kwargs.get('pk') or kwargs.get('id')
            
            try:
                # Execute the view
                response = view_func(*args, **kwargs)
                
                # Log data access
                log_data_access(
                    model_name,
                    operation,
                    record_id=str(record_id) if record_id else None,
                    user=user,
                    details={
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                    }
                )
                
                return response
                
            except Exception as e:
                # Log failed data access
                log_data_access(
                    model_name,
                    operation,
                    record_id=str(record_id) if record_id else None,
                    user=user,
                    details={
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "error": str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator

def audit_performance(metric_name: str = None):
    """
    Decorator to log performance metrics for views
    Works with both function-based and class-based views
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs) -> HttpResponse:
            start_time = time.time()
            metric_name_final = metric_name or f"{view_func.__name__}_duration"
            
            # Determine if this is a class-based view or function-based view
            if len(args) >= 2 and hasattr(args[0], 'request'):
                # This is a class-based view method (self, request, ...)
                request = args[1]
            elif len(args) >= 1 and hasattr(args[0], 'method'):
                # This is a function-based view (request, ...)
                request = args[0]
            else:
                # Fallback: try to find request in kwargs
                request = kwargs.get('request')
                if not request:
                    # If we can't find request, just execute the view without logging
                    return view_func(*args, **kwargs)
            
            try:
                # Execute the view
                response = view_func(*args, **kwargs)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Log performance metric
                audit_logger.log_performance_metric(
                    metric_name_final,
                    duration * 1000,  # Convert to milliseconds
                    "ms",
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                    }
                )
                
                return response
                
            except Exception as e:
                # Calculate duration even for failed requests
                duration = time.time() - start_time
                
                # Log performance metric for failed request
                audit_logger.log_performance_metric(
                    metric_name_final,
                    duration * 1000,  # Convert to milliseconds
                    "ms",
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "error": str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator

def audit_security_event(event_type: str, severity: str = "INFO"):
    """
    Decorator to log security events
    Works with both function-based and class-based views
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs) -> HttpResponse:
            # Determine if this is a class-based view or function-based view
            if len(args) >= 2 and hasattr(args[0], 'request'):
                # This is a class-based view method (self, request, ...)
                request = args[1]
            elif len(args) >= 1 and hasattr(args[0], 'method'):
                # This is a function-based view (request, ...)
                request = args[0]
            else:
                # Fallback: try to find request in kwargs
                request = kwargs.get('request')
                if not request:
                    # If we can't find request, just execute the view without logging
                    return view_func(*args, **kwargs)
            
            user = request.user if hasattr(request, 'user') else None
            
            try:
                # Execute the view
                response = view_func(*args, **kwargs)
                
                # Log security event
                audit_logger.log_security_event(
                    event_type,
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                        "action": "successful_access",
                    },
                    user=user,
                    severity=severity
                )
                
                return response
                
            except Exception as e:
                # Log security event for failed access
                audit_logger.log_security_event(
                    event_type,
                    {
                        "view": view_func.__name__,
                        "method": request.method,
                        "path": request.path,
                        "error": str(e),
                        "action": "failed_access",
                    },
                    user=user,
                    severity="ERROR"
                )
                raise
        
        return wrapper
    return decorator
