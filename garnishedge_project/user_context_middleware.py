"""
Custom middleware to maintain user context for model audit logging
"""
import threading
from django.utils.deprecation import MiddlewareMixin

# Global thread-local storage for user context
_thread_locals = threading.local()

class UserContextMiddleware(MiddlewareMixin):
    """
    Middleware to maintain user context across the request lifecycle
    This ensures model signals can access the current user
    """
    
    def process_request(self, request):
        """Set the current user in thread local storage"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            _thread_locals.user = request.user
        else:
            # Clear any existing user if not authenticated
            if hasattr(_thread_locals, 'user'):
                delattr(_thread_locals, 'user')
    
    def process_response(self, request, response):
        """Clean up thread local storage"""
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')
        return response
    
    def process_exception(self, request, exception):
        """Clean up thread local storage on exception"""
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')
        return None

def get_current_user():
    """
    Get the current user from thread local storage
    """
    try:
        user = getattr(_thread_locals, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            return user
        return None
    except:
        return None

def set_current_user(user):
    """
    Set the current user in thread local storage
    """
    try:
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            _thread_locals.user = user
        else:
            if hasattr(_thread_locals, 'user'):
                delattr(_thread_locals, 'user')
    except:
        pass

