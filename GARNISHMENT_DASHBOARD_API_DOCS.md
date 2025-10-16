# Garnishment Dashboard API Documentation

## Overview

The Garnishment Dashboard API provides comprehensive KPI (Key Performance Indicator) data for garnishment orders with advanced filtering capabilities. This API replaces the static dashboard implementation with dynamic, database-driven calculations.

## Endpoint

```
GET /utility/garnishment-dashboard/
```

## Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `garnishment_type` | String | Filter by garnishment type name (case-insensitive partial match) | `?garnishment_type=Child Support` or `?garnishment_type=tax` |
| `client_name` | String | Filter by client name or client ID (accepts both) | `?client_name=ABC Corp` or `?client_name=123` |
| `start_date` | Date (YYYY-MM-DD) | Filter orders created from this date | `?start_date=2024-01-01` |
| `end_date` | Date (YYYY-MM-DD) | Filter orders created until this date | `?end_date=2024-12-31` |

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Dashboard data retrieved successfully",
  "status_code": 200,
  "data": {
    "total_active_garnishment": 150,
    "total_garnished_employees": 120,
    "average_orders_per_employee": 1.25,
    "garnishment_type_breakdown": [
      {
        "garnishment_type": "Child Support",
        "count": 75,
        "percentage": 50.0
      },
      {
        "garnishment_type": "Tax Levy",
        "count": 45,
        "percentage": 30.0
      },
      {
        "garnishment_type": "Creditor Debt",
        "count": 30,
        "percentage": 20.0
      }
    ],
    "filters_applied": {
      "garnishment_type": "Child Support",
      "client_name": "ABC Corp",
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    }
  }
}
```

### Error Response (400 Bad Request)

```json
{
  "error": "Invalid start_date format. Use YYYY-MM-DD",
  "status_code": 400
}
```

**Note**: The API now accepts human-readable names instead of database IDs:
- `garnishment_type` accepts names like "Child Support", "Tax Levy", "Creditor Debt" (case-insensitive, partial matches supported)
- `client_name` accepts either client names like "ABC Corporation" or client IDs like "123" (automatically detects format)

### Error Response (500 Internal Server Error)

```json
{
  "error": "Error retrieving dashboard data: [error details]",
  "status_code": 500
}
```

## KPI Calculations

### 1. Total Active Garnishment
- **Definition**: Count of all garnishment orders with 'Active' status
- **Logic**: Orders that have a `start_date` and either no `stop_date` or `stop_date` is in the future
- **Calculation**: `COUNT(*) WHERE start_date IS NOT NULL AND (stop_date IS NULL OR stop_date > today)`

### 2. Total Garnished Employees
- **Definition**: Count of distinct employees who have garnishment orders
- **Logic**: Unique count of employees in the filtered garnishment orders
- **Calculation**: `COUNT(DISTINCT employee_id)`

### 3. Average Orders Per Employee
- **Definition**: Total Active Orders / Total Garnished Employees
- **Logic**: Division of total active garnishment by total garnished employees
- **Calculation**: `total_active_garnishment / total_garnished_employees`
- **Note**: Returns 0 if no garnished employees exist

### 4. Garnishment Type Breakdown
- **Definition**: Percentage breakdown of all active orders by garnishment type
- **Logic**: Groups active orders by garnishment type and calculates percentages
- **Calculation**: `(count_per_type / total_active_garnishment) * 100`
- **Order**: Results sorted by count (highest to lowest)

## Usage Examples

### 1. Basic Dashboard Data (No Filters)
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/"
```

### 2. Filter by Client Name
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/?client_name=ABC Corporation"
```

### 3. Filter by Client ID
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/?client_name=123"
```

### 4. Filter by Garnishment Type
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/?garnishment_type=Child Support"
```

### 5. Filter by Date Range
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/?start_date=2024-01-01&end_date=2024-12-31"
```

### 6. Combined Filters
```bash
curl -X GET "http://localhost:8000/utility/garnishment-dashboard/?client_name=ABC Corp&garnishment_type=Tax&start_date=2024-01-01&end_date=2024-12-31"
```

## Data Model Dependencies

The API relies on the following models:

- **GarnishmentOrder**: Primary model for garnishment orders
- **EmployeeDetail**: Employee information linked to garnishment orders
- **GarnishmentType**: Garnishment type definitions
- **Client**: Client information for filtering

## Performance Considerations

- The API uses `select_related()` for efficient database queries
- Filters are applied at the database level for optimal performance
- Distinct counting is used for accurate employee counts
- Results are ordered by count for garnishment type breakdown

## Error Handling

- **Invalid date format**: Returns 400 Bad Request with format guidance
- **Database errors**: Returns 500 Internal Server Error with error details
- **Missing parameters**: Gracefully handled (no error, just no filtering)
- **Invalid garnishment_type/client_name**: No error returned, just no matching results

**Note**: The API now uses case-insensitive partial matching for garnishment types and client names, making it more user-friendly and forgiving of typos.

## Migration from Old Dashboard

The new API replaces the static `get_dashboard_data` function with:

### Old Response Format
```json
{
  "success": true,
  "message": "Data Get Successfully",
  "status code": 200,
  "data": {
    "Total_IWO": 100,
    "Employees_with_Single_IWO": 80,
    "Employees_with_Multiple_IWO": 20,
    "Active_employees": 90
  }
}
```

### New Response Format
```json
{
  "success": true,
  "message": "Dashboard data retrieved successfully",
  "status_code": 200,
  "data": {
    "total_active_garnishment": 150,
    "total_garnished_employees": 120,
    "average_orders_per_employee": 1.25,
    "garnishment_type_breakdown": [...],
    "filters_applied": {...}
  }
}
```

## Testing

Use the provided test script `test_dashboard_api.py` to validate the API implementation:

```bash
python test_dashboard_api.py
```

Make sure to update the `BASE_URL` variable in the test script to match your server configuration.

## Future Enhancements

Potential improvements for future versions:

1. **Pagination**: For large datasets
2. **Caching**: Redis-based caching for frequently accessed data
3. **Real-time Updates**: WebSocket support for live dashboard updates
4. **Export Functionality**: CSV/Excel export capabilities
5. **Advanced Filtering**: More filter options (state, date ranges for different fields)
6. **Historical Data**: Time-series analysis capabilities
