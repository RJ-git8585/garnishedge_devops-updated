"""
Django model signals for automatic audit logging
"""
import json
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction

# Store original values for comparison
_original_values = {}

@receiver(pre_save)
def store_original_values(sender, instance, **kwargs):
    """
    Store original values before save for comparison
    """
    if hasattr(instance, 'pk') and instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            _original_values[instance.pk] = {
                'model': sender.__name__,
                'values': {
                    field.name: getattr(original, field.name)
                    for field in original._meta.fields
                    if hasattr(original, field.name)
                }
            }
        except sender.DoesNotExist:
            pass

@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """
    Log model creation and updates
    """
    from .model_audit import log_model_create, log_model_update
    
    # Get the current user from thread local storage or request
    user = get_current_user()
    
    # Fallback: try to get user from request context if available
    if not user:
        user = get_user_from_request_context()
    
    model_name = sender.__name__
    object_id = str(instance.pk)
    
    if created:
        # Log creation
        new_values = {
            field.name: getattr(instance, field.name)
            for field in instance._meta.fields
            if hasattr(instance, field.name)
        }
        
        log_model_create(
            model_name=model_name,
            object_id=object_id,
            user=user,
            new_values=new_values
        )
    else:
        # Log update
        original_data = _original_values.get(instance.pk, {})
        old_values = original_data.get('values', {})
        
        # Calculate changes
        changes = {}
        for field in instance._meta.fields:
            if hasattr(instance, field.name):
                field_name = field.name
                old_value = old_values.get(field_name)
                new_value = getattr(instance, field_name)
                
                if old_value != new_value:
                    changes[field_name] = {
                        'old': old_value,
                        'new': new_value
                    }
        
        if changes:  # Only log if there were actual changes
            new_values = {
                field.name: getattr(instance, field.name)
                for field in instance._meta.fields
                if hasattr(instance, field.name)
            }
            
            log_model_update(
                model_name=model_name,
                object_id=object_id,
                user=user,
                changes=changes,
                old_values=old_values,
                new_values=new_values
            )
        
        # Clean up stored values
        _original_values.pop(instance.pk, None)

@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """
    Log model deletion
    """
    from .model_audit import log_model_delete
    
    user = get_current_user()
    
    # Fallback: try to get user from request context if available
    if not user:
        user = get_user_from_request_context()
    
    model_name = sender.__name__
    object_id = str(instance.pk)
    
    # Get the values before deletion
    old_values = {
        field.name: getattr(instance, field.name)
        for field in instance._meta.fields
        if hasattr(instance, field.name)
    }
    
    log_model_delete(
        model_name=model_name,
        object_id=object_id,
        user=user,
        old_values=old_values
    )

def get_current_user():
    """
    Get the current user from thread local storage
    This is set by our middleware
    """
    try:
        from .user_context_middleware import get_current_user as middleware_get_user
        return middleware_get_user()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_current_user: {e}")
        return None

def set_current_user(user):
    """
    Set the current user in thread local storage
    This is called by our middleware
    """
    try:
        from .user_context_middleware import set_current_user as middleware_set_user
        middleware_set_user(user)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in set_current_user: {e}")

def get_user_from_request_context():
    """
    Fallback method to get user from request context
    This tries to get the user from the current request if available
    """
    try:
        from django.contrib.auth import get_user_model
        from django.utils import deprecation
        
        # Try to get user from current request context
        # This is a fallback when thread locals don't work
        User = get_user_model()
        
        # Try to get from request if available in context
        # This is a more reliable approach using Django's request context
        try:
            from django.utils.deprecation import MiddlewareMixin
            # Check if we're in a request context
            from django.utils import deprecation
            if hasattr(deprecation, 'current_request'):
                request = deprecation.current_request
                if request and hasattr(request, 'user'):
                    user = request.user
                    if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
                        return user
        except:
            pass
        
        return None
    except:
        return None
