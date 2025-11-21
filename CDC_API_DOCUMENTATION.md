# CDC (Change Data Capture) API Documentation

## Overview

The CDC API provides access to audit logs from Azure SQL Database's Change Data Capture (CDC) system. It allows you to query change history filtered by user, table, operation type, and time range. CDC automatically tracks all INSERT, UPDATE, and DELETE operations on configured tables without requiring any Django models.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Configuration](#configuration)
3. [API Endpoint](#api-endpoint)
4. [Request Parameters](#request-parameters)
5. [Response Format](#response-format)
6. [Examples](#examples)
7. [How It Works](#how-it-works)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Enable CDC on Azure SQL Database

Before using this API, you must enable CDC on your Azure SQL Database tables:

```sql
-- Enable CDC on the database
EXEC sys.sp_cdc_enable_db;

-- Enable CDC on a specific table
EXEC sys.sp_cdc_enable_table
    @source_schema = N'dbo',
    @source_name = N'GarnishmentOrder',
    @role_name = N'cdc_admin',
    @capture_instance = N'dbo_GarnishmentOrder';
```

**Important Notes:**
- The `@capture_instance` name is what you'll use in the configuration
- CDC automatically creates system tables under the `cdc` schema
- The table must have a `modified_by` column (or your custom user tracking column)

### 2. Database Configuration

Ensure your `DATABASES['default']` in `settings.py` points to Azure SQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': env('AZURE_DB_NAME'),
        'USER': env('AZURE_DB_USER'),
        'PASSWORD': env('AZURE_DB_PASSWORD'),
        'HOST': env('AZURE_DB_HOST'),
        'PORT': env('AZURE_DB_PORT'),
        'OPTIONS': {
            'driver': env('AZURE_DB_DRIVER'),
            'Encrypt': 'yes',
            'TrustServerCertificate': 'no',
        }
    }
}
```

---

## Configuration

### Setting Up CDC_CAPTURE_INSTANCES

Configure which CDC capture instances the API can access via the `CDC_CAPTURE_INSTANCES` environment variable (JSON format):

```json
CDC_CAPTURE_INSTANCES={
  "garnishment_order": {
    "capture_instance": "dbo_GarnishmentOrder",
    "table_name": "dbo.GarnishmentOrder",
    "user_column": "modified_by",
    "select_columns": ["order_number", "employee_id", "status", "amount"]
  },
  "employee": {
    "capture_instance": "dbo_Employee",
    "table_name": "dbo.Employee",
    "user_column": "modified_by",
    "select_columns": ["employee_id", "first_name", "last_name", "email"]
  },
  "payroll": {
    "capture_instance": "dbo_Payroll",
    "table_name": "dbo.Payroll",
    "user_column": "updated_by",
    "select_columns": ["payroll_id", "employee_id", "amount", "pay_period"]
  },
  "garnishment_type": {
    "capture_instance": "dbo_garnishment_type",
    "table_name": "dbo.garnishment_type",
    "user_column": "modified_by",
    "select_columns": ["id", "code", "type", "description", "report_description", "pay_stub_description"]
  },
  "pay_period": {
    "capture_instance": "dbo_payperiod",
    "table_name": "dbo.payperiod",
    "user_column": "modified_by",
    "select_columns": ["pp_id", "name"]
  }
}
```

### Configuration Fields

- **`capture_instance`** (required): The CDC capture instance name (matches `@capture_instance` from SQL)
- **`table_name`** (optional): Display name for the table (defaults to `capture_instance`)
- **`user_column`** (optional): Column name that stores the user ID (defaults to `"modified_by"`)
- **`select_columns`** (optional): Array of additional columns to include in the response payload

### Environment Variable Setup

Set the environment variable in your production environment:

```bash
export CDC_CAPTURE_INSTANCES='{"garnishment_order":{"capture_instance":"dbo_GarnishmentOrder","table_name":"dbo.GarnishmentOrder","user_column":"modified_by","select_columns":["order_number","employee_id","status"]}}'
```

Or in your `.env` file:

```
CDC_CAPTURE_INSTANCES={"garnishment_order":{"capture_instance":"dbo_GarnishmentOrder","table_name":"dbo.GarnishmentOrder","user_column":"modified_by","select_columns":["order_number","employee_id","status"]}}
```

---

## API Endpoint

### Base URL

```
GET /log/cdc/<user_id>/
```

### Authentication

Requires JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### URL Parameters

- **`user_id`** (path parameter, required): The user ID to filter CDC logs by (maps to `modified_by` column)

---

## Request Parameters

All parameters are optional query parameters:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | string | No | `"all"` | CDC capture instance key (from config) or `"all"` for all tables |
| `start_at` | datetime | No | - | UTC timestamp (ISO-8601) for earliest changes |
| `end_at` | datetime | No | - | UTC timestamp (ISO-8601) for latest changes |
| `operation` | string | No | - | Filter by operation: `"insert"`, `"delete"`, `"update_after"`, `"update_before"` |
| `limit` | integer | No | `500` | Maximum number of results (1-2000) |

### Operation Types

- **`insert`**: New records inserted
- **`delete`**: Records deleted
- **`update_before`**: State before update (old values)
- **`update_after`**: State after update (new values)

---

## Response Format

### Success Response (200 OK)

```json
{
  "count": 150,
  "source": "all",
  "user_id": 42,
  "results": [
    {
      "table": "dbo.GarnishmentOrder",
      "source_key": "garnishment_order",
      "changed_at": "2024-01-15T10:30:00",
      "operation": "update_after",
      "modified_by": 42,
      "start_lsn": "00000123:00000045:0001",
      "sequence_value": "00000123:00000045:0002",
      "payload": {
        "order_number": "ORD-12345",
        "employee_id": 789,
        "status": "active",
        "amount": 500.00
      }
    },
    {
      "table": "dbo.Employee",
      "source_key": "employee",
      "changed_at": "2024-01-15T09:15:00",
      "operation": "insert",
      "modified_by": 42,
      "start_lsn": "00000122:00000030:0001",
      "sequence_value": "00000122:00000030:0002",
      "payload": {
        "employee_id": 789,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com"
      }
    }
  ]
}
```

### Response Fields

- **`count`**: Total number of results returned
- **`source`**: The source key used (`"all"` or specific table key)
- **`user_id`**: The user ID from the URL path
- **`results`**: Array of change log entries, each containing:
  - **`table`**: Display name of the table
  - **`source_key`**: Configuration key for this table
  - **`changed_at`**: Timestamp when the change occurred
  - **`operation`**: Type of operation performed
  - **`modified_by`**: User ID who made the change
  - **`start_lsn`**: Log Sequence Number (hex format)
  - **`sequence_value`**: Sequence value for ordering
  - **`payload`**: Additional columns specified in `select_columns`

### Error Responses

#### 400 Bad Request
```json
{
  "detail": "Unable to read CDC logs for 'dbo_GarnishmentOrder': Invalid capture instance."
}
```

#### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### 501 Not Implemented
```json
{
  "detail": "The CDC log endpoint requires an Azure SQL / SQL Server backend.",
  "hint": "Switch DATABASES['default'] to the Azure SQL instance in production."
}
```

---

## Examples

### Example 1: Get All Changes for a User

```bash
GET /log/cdc/42/
```

Returns all CDC logs for user 42 across all configured tables.

### Example 2: Get Changes from Specific Table

```bash
GET /log/cdc/42/?source=garnishment_order
```

Returns CDC logs for user 42 from the `garnishment_order` table only.

### Example 3: Filter by Time Range

```bash
GET /log/cdc/42/?start_at=2024-01-01T00:00:00Z&end_at=2024-01-31T23:59:59Z
```

Returns changes for user 42 within January 2024.

### Example 4: Filter by Operation Type

```bash
GET /log/cdc/42/?operation=update_after&limit=100
```

Returns only update operations (after state) for user 42, limited to 100 results.

### Example 5: Combined Filters

```bash
GET /log/cdc/42/?source=garnishment_order&operation=insert&start_at=2024-01-15T00:00:00Z&limit=50
```

Returns insert operations for user 42 in the `garnishment_order` table since January 15, 2024, limited to 50 results.

### Example 6: Using cURL

```bash
curl -X GET "https://api.example.com/log/cdc/42/?source=all&limit=200" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

### Example 7: Using Python Requests

```python
import requests

url = "https://api.example.com/log/cdc/42/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
params = {
    "source": "all",
    "start_at": "2024-01-01T00:00:00Z",
    "limit": 100
}

response = requests.get(url, headers=headers, params=params)
data = response.json()
print(f"Found {data['count']} changes")
for change in data['results']:
    print(f"{change['table']}: {change['operation']} at {change['changed_at']}")
```

---

## How It Works

### Architecture Overview

1. **CDC System Tables**: Azure SQL automatically maintains CDC change data in system tables under the `cdc` schema when CDC is enabled on a table.

2. **No Django Models Required**: The API doesn't use Django ORM models. Instead, it executes raw SQL queries directly against CDC system functions.

3. **Direct SQL Queries**: The view uses Django's database cursor to execute CDC table-valued functions:
   ```sql
   SELECT ... FROM cdc.fn_cdc_get_all_changes_{capture_instance}(start_lsn, end_lsn, 'all')
   ```

4. **LSN Mapping**: Time-based filtering works by converting timestamps to Log Sequence Numbers (LSNs) using SQL Server functions:
   - `sys.fn_cdc_map_time_to_lsn()` - Converts timestamp to LSN
   - `sys.fn_cdc_map_lsn_to_time()` - Converts LSN back to timestamp

5. **Aggregation**: When `source=all`, the API:
   - Loops through all configured capture instances
   - Queries each one separately
   - Aggregates results
   - Sorts by `changed_at` (most recent first)
   - Applies the global limit

### Data Flow

```
User Request
    ↓
ChangeLogAPIView.get()
    ↓
Validate query parameters
    ↓
Check database engine (must be SQL Server/Azure SQL)
    ↓
If source="all":
    ├─ Loop through all CDC_CAPTURE_INSTANCES
    ├─ For each: _fetch_cdc_rows()
    ├─ Aggregate results
    └─ Sort by changed_at DESC
Else:
    └─ _fetch_cdc_rows() for single table
    ↓
Execute CDC SQL function
    ↓
Filter by user_id, operation, time range
    ↓
Serialize results
    ↓
Return JSON response
```

### Key SQL Functions Used

- **`cdc.fn_cdc_get_all_changes_{capture_instance}`**: Retrieves all changes for a capture instance
- **`sys.fn_cdc_get_min_lsn`**: Gets the minimum LSN for a capture instance
- **`sys.fn_cdc_get_max_lsn`**: Gets the maximum LSN (database-wide)
- **`sys.fn_cdc_map_time_to_lsn`**: Converts timestamp to LSN for filtering
- **`sys.fn_cdc_map_lsn_to_time`**: Converts LSN to timestamp for display

---

## Troubleshooting

### Issue: "The CDC log endpoint requires an Azure SQL / SQL Server backend"

**Cause**: Your `DATABASES['default']` is pointing to PostgreSQL or another database.

**Solution**: Update `settings.py` to use Azure SQL configuration in production.

### Issue: "No CDC capture instances configured"

**Cause**: The `CDC_CAPTURE_INSTANCES` environment variable is empty or not set.

**Solution**: Set the `CDC_CAPTURE_INSTANCES` environment variable with your CDC configuration.

### Issue: "Unable to read CDC logs for 'X': Invalid capture instance"

**Cause**: The capture instance name doesn't exist in your Azure SQL database.

**Solution**: 
1. Verify CDC is enabled on the table: `SELECT * FROM cdc.change_tables WHERE capture_instance = 'X'`
2. Check the capture instance name matches exactly (case-sensitive)
3. Ensure the user has permissions to access CDC tables

### Issue: No results returned

**Possible Causes**:
1. No changes exist for the specified user_id
2. Time range is outside the CDC retention period
3. The `modified_by` column doesn't match the user_id

**Solution**:
1. Verify CDC is capturing data: `SELECT COUNT(*) FROM cdc.dbo_GarnishmentOrder_CT`
2. Check if the user_id exists in the `modified_by` column
3. Expand the time range or remove time filters

### Issue: Performance Issues with `source=all`

**Cause**: Querying all tables can be slow if you have many capture instances or large datasets.

**Solution**:
1. Use specific `source` parameter when possible
2. Add time range filters to limit the scope
3. Reduce the `limit` parameter
4. Consider adding indexes on CDC tables (if allowed by Azure SQL)

### Verifying CDC Setup

Run these SQL queries to verify CDC is properly configured:

```sql
-- Check if CDC is enabled on database
SELECT is_cdc_enabled FROM sys.databases WHERE name = 'YourDatabaseName';

-- List all CDC capture instances
SELECT * FROM cdc.change_tables;

-- Check CDC capture instance details
SELECT * FROM cdc.change_tables WHERE capture_instance = 'dbo_GarnishmentOrder';

-- View recent changes (example)
SELECT TOP 10 * FROM cdc.dbo_GarnishmentOrder_CT ORDER BY __$start_lsn DESC;
```

---

## Security Considerations

1. **Authentication**: The endpoint requires JWT authentication (`IsAuthenticated` permission).

2. **SQL Injection Protection**: 
   - Capture instance names are validated against `CDC_CAPTURE_INSTANCES` configuration
   - All user inputs are parameterized in SQL queries
   - Column names are validated before use

3. **User Filtering**: The `user_id` in the URL path ensures users can only query their own audit logs (or admins can query specific users).

4. **Rate Limiting**: Consider adding rate limiting to prevent abuse (already configured in DRF settings).

---

## Best Practices

1. **Configure Only Necessary Tables**: Only enable CDC on tables that need audit logging to reduce overhead.

2. **Set Appropriate Limits**: Use reasonable `limit` values to prevent large responses.

3. **Use Time Ranges**: Always specify `start_at` and `end_at` when querying historical data to improve performance.

4. **Monitor CDC Retention**: CDC data has retention limits. Query within the retention window.

5. **Index Considerations**: Ensure your base tables have indexes on `modified_by` and timestamp columns for better CDC query performance.

---

## Additional Resources

- [Azure SQL Change Data Capture Documentation](https://docs.microsoft.com/en-us/sql/relational-databases/track-changes/about-change-data-capture-sql-server)
- [SQL Server CDC Functions](https://docs.microsoft.com/en-us/sql/relational-databases/system-functions/change-data-capture-functions-transact-sql)
- [Django REST Framework Documentation](https://www.django-rest-framework.org/)

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify your CDC setup in Azure SQL
3. Review the API logs for detailed error messages
4. Contact your DevOps team for database configuration assistance

