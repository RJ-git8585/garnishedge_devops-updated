"""
Model Audit Logging System
Tracks all CRUD operations on models with detailed change tracking
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from django.db.models import Model
from django.db import transaction
from opentelemetry import trace
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

class AuditJSONEncoder(DjangoJSONEncoder):
    """
    Custom JSON encoder for audit logging that handles Django models and other objects
    """
    def default(self, obj):
        if isinstance(obj, Model):
            # For Django models, return a dictionary with basic info
            return {
                'model': obj.__class__.__name__,
                'id': str(obj.pk) if obj.pk else None,
                'str': str(obj)
            }
        elif hasattr(obj, '__dict__'):
            # For other objects with attributes, try to serialize their dict
            try:
                return obj.__dict__
            except:
                return str(obj)
        else:
            # Fall back to string representation
            return str(obj)

class ModelAuditLogger:
    """
    Comprehensive model audit logging system
    """
    
    def __init__(self):
        from .audit_logger import audit_logger
        self.audit_logger = audit_logger
    
    def log_model_operation(self, 
                          action: str, 
                          model_name: str, 
                          object_id: str, 
                          user = None,
                          changes: Dict[str, Any] = None,
                          old_values: Dict[str, Any] = None,
                          new_values: Dict[str, Any] = None):
        """
        Log a model operation with detailed information
        
        Args:
            action: CREATE, UPDATE, DELETE, READ
            model_name: Name of the model (e.g., 'Employee', 'User')
            object_id: ID of the object being modified
            user: User performing the action
            changes: Dictionary of changes made
            old_values: Previous values (for UPDATE)
            new_values: New values (for CREATE/UPDATE)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = user.username if user and user.is_authenticated else "anonymous"
        
        # Format changes for display
        changes_display = self._format_changes(changes, old_values, new_values, action)
        
        # Create audit record
        audit_record = {
            "timestamp": timestamp,
            "user": username,
            "action": action,
            "model": model_name,
            "object_id": str(object_id),
            "changes": changes_display,
            "user_id": str(user.id) if user and user.is_authenticated else None,
            "ip_address": self._get_current_ip(),
            "session_id": self._get_session_id()
        }
        
        # Log to file
        self._log_to_file(audit_record)
        
        # Log to OpenTelemetry
        self._log_to_telemetry(audit_record)
        
        # Log to audit logger
        self.audit_logger.log_data_access(
            model_name,
            action,
            record_id=str(object_id),
            user=user,
            details=audit_record
        )
    
    def _format_changes(self, changes: Dict[str, Any], old_values: Dict[str, Any], 
                       new_values: Dict[str, Any], action: str) -> str:
        """Format changes for display"""
        if action == "CREATE":
            if new_values:
                return json.dumps(new_values, indent=2, cls=AuditJSONEncoder)
            return "{}"
        
        elif action == "UPDATE":
            if changes:
                formatted_changes = {}
                for field, change in changes.items():
                    if isinstance(change, dict) and 'old' in change and 'new' in change:
                        formatted_changes[field] = f"{change['old']} → {change['new']}"
                    else:
                        formatted_changes[field] = change
                return json.dumps(formatted_changes, indent=2, cls=AuditJSONEncoder)
            return "{}"
        
        elif action == "DELETE":
            if old_values:
                return json.dumps(old_values, indent=2, cls=AuditJSONEncoder)
            return "{}"
        
        return "{}"
    
    def _get_current_ip(self) -> str:
        """Get current IP address from request context"""
        try:
            from django.utils.deprecation import MiddlewareMixin
            # This would be set by middleware
            return getattr(self, '_current_ip', 'unknown')
        except:
            return 'unknown'
    
    def _get_session_id(self) -> str:
        """Get current session ID"""
        try:
            from django.utils.deprecation import MiddlewareMixin
            # This would be set by middleware
            return getattr(self, '_session_id', 'unknown')
        except:
            return 'unknown'
    
    def _log_to_file(self, audit_record: Dict[str, Any]):
        """Log to dedicated audit file"""
        audit_logger = logging.getLogger('model_audit')
        
        # Format as table row
        log_message = (
            f"| {audit_record['timestamp']:<15} | "
            f"{audit_record['user']:<8} | "
            f"{audit_record['action']:<6} | "
            f"{audit_record['model']:<8} | "
            f"{audit_record['object_id']:<8} | "
            f"{audit_record['changes']:<25} |"
        )
        
        audit_logger.info(log_message)
    
    def _log_to_telemetry(self, audit_record: Dict[str, Any]):
        """Log to OpenTelemetry spans"""
        span = trace.get_current_span()
        if span and span.is_recording():
            # Add attributes to current span
            span.set_attribute("audit.timestamp", audit_record['timestamp'])
            span.set_attribute("audit.user", audit_record['user'])
            span.set_attribute("audit.action", audit_record['action'])
            span.set_attribute("audit.model", audit_record['model'])
            span.set_attribute("audit.object_id", audit_record['object_id'])
            span.set_attribute("audit.changes", audit_record['changes'])
            
            # Add audit event
            from .otel_config import add_audit_event
            add_audit_event(span, "model.audit", audit_record)

# Global instance
model_audit_logger = ModelAuditLogger()

# Convenience functions
def log_model_create(model_name: str, object_id: str, user = None, 
                    new_values: Dict[str, Any] = None):
    """Log model creation"""
    model_audit_logger.log_model_operation(
        action="CREATE",
        model_name=model_name,
        object_id=object_id,
        user=user,
        new_values=new_values
    )

def log_model_update(model_name: str, object_id: str, user = None,
                    changes: Dict[str, Any] = None, old_values: Dict[str, Any] = None,
                    new_values: Dict[str, Any] = None):
    """Log model update"""
    model_audit_logger.log_model_operation(
        action="UPDATE",
        model_name=model_name,
        object_id=object_id,
        user=user,
        changes=changes,
        old_values=old_values,
        new_values=new_values
    )

def log_model_delete(model_name: str, object_id: str, user = None,
                    old_values: Dict[str, Any] = None):
    """Log model deletion"""
    model_audit_logger.log_model_operation(
        action="DELETE",
        model_name=model_name,
        object_id=object_id,
        user=user,
        old_values=old_values
    )

def log_model_read(model_name: str, object_id: str, user = None):
    """Log model read access"""
    model_audit_logger.log_model_operation(
        action="READ",
        model_name=model_name,
        object_id=object_id,
        user=user
    )
