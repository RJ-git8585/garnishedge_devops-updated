# OpenTelemetry Audit Logging Implementation

This document describes the comprehensive audit logging implementation using OpenTelemetry for the Garnishedge API.

## Overview

The audit logging system provides:
- **Complete API call tracking** with request/response details
- **Business operation logging** for audit trails
- **Data access monitoring** for compliance
- **Security event logging** for threat detection
- **Performance metrics** for optimization
- **Distributed tracing** across services

## Architecture

```
Django App → OpenTelemetry SDK → OTLP Collector → Jaeger/Prometheus/Elasticsearch
```

## Components

### 1. OpenTelemetry Configuration (`garnishedge_project/otel_config.py`)
- Configures OpenTelemetry SDK
- Sets up exporters (Jaeger, OTLP)
- Provides utility functions for span management

### 2. Audit Middleware (`garnishedge_project/audit_middleware.py`)
- `AuditLoggingMiddleware`: Logs all HTTP requests/responses
- `DatabaseAuditMiddleware`: Tracks database operations

### 3. Audit Logger (`garnishedge_project/audit_logger.py`)
- Comprehensive logging utilities
- Business operation tracking
- Security event logging
- Performance metrics

### 4. Audit Decorators (`garnishedge_project/audit_decorators.py`)
- Easy-to-use decorators for views
- Automatic audit logging
- Customizable operation tracking

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Add to your `.env` file:

```env
# OpenTelemetry Configuration
OTLP_ENDPOINT=http://localhost:4317
JAEGER_ENDPOINT=http://localhost:14268/api/traces
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831
ENVIRONMENT=development
```

### 3. Start OpenTelemetry Infrastructure

```bash
# Start Jaeger, Prometheus, Grafana, etc.
docker-compose -f docker-compose.otel.yml up -d
```

### 4. Create Logs Directory

```bash
mkdir -p logs
```

### 5. Test Configuration

```bash
python manage.py test_otel
```

## Usage Examples

### 1. Using Decorators (Recommended)

```python
from garnishedge_project.audit_decorators import (
    audit_api_call, 
    audit_business_operation, 
    audit_data_access
)

class EmployeeView(APIView):
    @audit_api_call
    @audit_business_operation("employee_retrieval")
    @audit_data_access("Employee", "READ")
    def get(self, request):
        # Your view logic
        return Response({"data": "employee_data"})
```

### 2. Manual Logging

```python
from garnishedge_project.audit_logger import audit_logger

def my_view(request):
    # Log business operation
    audit_logger.log_business_operation(
        "employee_creation",
        {"employee_id": "123", "department": "HR"},
        user=request.user,
        success=True
    )
    
    # Log security event
    audit_logger.log_security_event(
        "data_access",
        {"model": "Employee", "action": "create"},
        user=request.user,
        severity="INFO"
    )
```

### 3. Custom Spans

```python
from garnishedge_project.otel_config import create_audit_span, add_audit_event

def complex_operation(request):
    with create_audit_span("complex_employee_processing") as span:
        span.set_attribute("operation.type", "bulk_import")
        
        add_audit_event(span, "processing.started", {
            "batch_size": 1000
        })
        
        # Your processing logic
        
        add_audit_event(span, "processing.completed", {
            "records_processed": 1000,
            "success": True
        })
```

## What Gets Logged

### API Calls
- Request method, URL, headers
- Request body (with size limits)
- Response status, headers, body (for errors)
- Client IP, user agent
- User information (if authenticated)
- Request duration
- Exceptions and errors

### Business Operations
- Operation name and type
- User performing the operation
- Success/failure status
- Custom details and metadata
- Timestamps

### Data Access
- Model name and operation (CRUD)
- Record IDs
- User performing the access
- Additional context

### Security Events
- Event type and severity
- User information
- IP addresses and user agents
- Security-related actions

### Performance Metrics
- Operation duration
- Database query counts
- Memory usage
- Custom metrics

## Monitoring and Visualization

### Jaeger UI
- **URL**: http://localhost:16686
- **Purpose**: Distributed tracing visualization
- **Features**: Trace search, span details, service maps

### Grafana
- **URL**: http://localhost:3000
- **Username**: admin
- **Password**: admin
- **Purpose**: Metrics and logs visualization

### Prometheus
- **URL**: http://localhost:9090
- **Purpose**: Metrics collection and querying

## Log Files

- `logs/audit.log`: General application logs with trace context
- `logs/api_audit.log`: Detailed API audit logs

## Integration with Existing Views

To add audit logging to existing views:

```python
# Option 1: Use decorators
from garnishedge_project.audit_decorators import audit_api_call

class ExistingView(APIView):
    @audit_api_call
    def get(self, request):
        # Existing code unchanged
        pass

# Option 2: Use the helper function
from garnishedge_project.audit_examples import add_audit_to_existing_view

# Apply to existing view class
add_audit_to_existing_view(ExistingView)
```

## Security Considerations

1. **Sensitive Data**: Headers and request bodies are filtered to remove sensitive information
2. **Data Retention**: Configure appropriate retention policies for your compliance needs
3. **Access Control**: Ensure monitoring systems have proper access controls
4. **PII Handling**: Be careful with personally identifiable information in logs

## Performance Impact

- **Minimal overhead**: OpenTelemetry is designed for production use
- **Async processing**: Spans are processed asynchronously
- **Configurable sampling**: Can be configured to reduce overhead if needed
- **Batch processing**: Multiple spans are batched for efficiency

## Troubleshooting

### Common Issues

1. **OpenTelemetry not initializing**
   - Check environment variables
   - Verify dependencies are installed
   - Check logs for configuration errors

2. **No traces in Jaeger**
   - Verify Jaeger is running
   - Check OTLP endpoint configuration
   - Ensure spans are being created

3. **High memory usage**
   - Adjust batch processor settings
   - Configure memory limits
   - Consider sampling for high-traffic applications

### Debug Commands

```bash
# Test OpenTelemetry configuration
python manage.py test_otel

# Check if Jaeger is accessible
curl http://localhost:16686/api/services

# View collector logs
docker logs otel-collector
```

## Production Considerations

1. **Resource Limits**: Configure appropriate memory and CPU limits
2. **Storage**: Plan for log and trace storage requirements
3. **Network**: Ensure proper network configuration for exporters
4. **Monitoring**: Monitor the monitoring system itself
5. **Backup**: Implement backup strategies for audit data

## Compliance Features

- **Complete audit trail** for all API calls
- **User attribution** for all operations
- **Data access logging** for compliance
- **Security event tracking** for threat detection
- **Immutable logs** (when using appropriate storage)
- **Searchable traces** for investigation

## Next Steps

1. **Custom Dashboards**: Create Grafana dashboards for your specific needs
2. **Alerting**: Set up alerts for security events and performance issues
3. **Integration**: Integrate with existing monitoring tools
4. **Sampling**: Configure sampling for high-traffic scenarios
5. **Retention**: Implement appropriate data retention policies


