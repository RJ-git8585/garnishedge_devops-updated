# Employee Garnishment API Documentation

This document describes the APIs for managing complete employee and garnishment order data in the user_app.

## API Endpoints

### 1. Get Employee and Garnishment Details by ee_id and client_id

**Endpoint:** `GET /api/employee/garnishment-details/{ee_id}/{client_id}/`

**Description:** Retrieves complete employee details along with garnishment order information based on employee ID and client ID.

**URL Parameters:**
- `ee_id` (required): Employee ID to fetch details for
- `client_id` (required): Client ID to filter employee

**Example Request:**
```
GET /api/employee/garnishment-details/EE3FEMJN/CLIENT001/
```

**Example Response:**
```json
{
    "success": true,
    "message": "Employee and garnishment details fetched successfully",
    "data": {
        "ee_id": "EE3FEMJN",
        "home_state": "kentucky",
        "work_state": "west virginia",
        "no_of_exemption_including_self": 1,
        "filing_status": "single",
        "age": 0,
        "is_blind": 0,
        "is_spouse_blind": 0,
        "spouse_age": 0,
        "no_of_student_default_loan": 0,
        "statement_of_exemption_received_date": "",
        "garn_start_date": "07/10/2025",
        "support_second_family": "",
        "arrears_greater_than_12_weeks": "",
        "no_of_dependent_child": 2,
        "consumer_debt": true,
        "non_consumer_debt": false,
        "garnishment_data": [
            {
                "type": "state tax levy",
                "data": [
                    {
                        "case_id": "C3FE4NL",
                        "ordered_amount": 0,
                        "arrear_amount": 0
                    }
                ]
            }
        ]
    },
    "status_code": 200
}
```

### 2. Update Employee Data

**Endpoint:** `PUT /api/employee/garnishment-update/{ee_id}/{client_id}/`

**Description:** Updates employee details based on employee ID and client ID.

**URL Parameters:**
- `ee_id` (required): Employee ID to update
- `client_id` (required): Client ID to filter employee

**Request Body:**
```json
{
    "first_name": "John",
    "last_name": "Doe",
    "number_of_exemptions": 2,
    "marital_status": "Married",
    "number_of_dependent_child": 1,
    "support_second_family": false,
    "garnishment_fees_status": true,
    "is_active": true
}
```

**Example Request:**
```
PUT /api/employee/garnishment-update/EE3FEMJN/CLIENT001/
Content-Type: application/json

{
    "first_name": "John",
    "last_name": "Doe",
    "number_of_exemptions": 2
}
```

**Example Response:**
```json
{
    "success": true,
    "message": "Employee data updated successfully",
    "data": {
        "ee_id": "EE3FEMJN",
        "home_state": "kentucky",
        "work_state": "west virginia",
        "no_of_exemption_including_self": 2,
        "filing_status": "single",
        "age": 0,
        "is_blind": 0,
        "is_spouse_blind": 0,
        "spouse_age": 0,
        "no_of_student_default_loan": 0,
        "statement_of_exemption_received_date": "",
        "garn_start_date": "07/10/2025",
        "support_second_family": "",
        "arrears_greater_than_12_weeks": "",
        "no_of_dependent_child": 2,
        "consumer_debt": true,
        "non_consumer_debt": false,
        "garnishment_data": [...]
    },
    "status_code": 200
}
```

### 3. List All Employees with Garnishment Details

**Endpoint:** `GET /api/employee/garnishment-list/`

**Description:** Retrieves a paginated list of all employees with their basic garnishment information.

**Query Parameters:**
- `page` (optional): Page number for pagination (default: 1)
- `page_size` (optional): Number of items per page (default: 20)
- `search` (optional): Search term for employee name or ee_id

**Example Request:**
```
GET /api/employee/garnishment-list/?page=1&page_size=10&search=John
```

**Example Response:**
```json
{
    "success": true,
    "message": "Employees with garnishment details fetched successfully",
    "data": {
        "results": [
            {
                "ee_id": "EE3FEMJN",
                "home_state": "kentucky",
                "work_state": "west virginia",
                "no_of_exemption_including_self": 1,
                "filing_status": "single",
                "age": 0,
                "is_blind": 0,
                "is_spouse_blind": 0,
                "spouse_age": 0,
                "no_of_student_default_loan": 0,
                "statement_of_exemption_received_date": "",
                "garn_start_date": "07/10/2025",
                "support_second_family": "",
                "arrears_greater_than_12_weeks": "",
                "no_of_dependent_child": 2,
                "consumer_debt": true,
                "non_consumer_debt": false,
                "garnishments": [...]
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 10,
            "total_count": 25,
            "total_pages": 3
        }
    },
    "status_code": 200
}
```

## Error Responses

All APIs return consistent error responses:

```json
{
    "success": false,
    "message": "Error message",
    "error": "Detailed error information",
    "status_code": 400
}
```

## Common Error Codes

- `400`: Bad Request - Missing required parameters or invalid data
- `404`: Not Found - Employee with specified ee_id not found
- `500`: Internal Server Error - Server-side error

## Data Models

### Employee Fields
- `ee_id`: Employee ID (unique)
- `home_state`: Home state code
- `work_state`: Work state code
- `no_of_exemption_including_self`: Number of tax exemptions including self
- `filing_status`: Tax filing status
- `age`: Employee age
- `is_blind`: Boolean flag for blindness
- `is_spouse_blind`: Boolean flag for spouse blindness
- `spouse_age`: Spouse age
- `no_of_student_default_loan`: Number of student loans
- `statement_of_exemption_received_date`: Date exemption statement was received
- `garn_start_date`: Garnishment start date
- `support_second_family`: Boolean flag for second family support
- `arrears_greater_than_12_weeks`: Boolean flag for arrears greater than 12 weeks
- `no_of_dependent_child`: Number of dependent children
- `consumer_debt`: Boolean flag for consumer debt
- `non_consumer_debt`: Boolean flag for non-consumer debt

### Garnishment Data Structure
- `type`: Type of garnishment (child_support, student_loan, state_tax_levy, etc.)
- `data`: Array of garnishment orders for this type
  - `case_id`: Unique case identifier
  - `ordered_amount`: Amount ordered to be garnished
  - `arrear_amount`: Arrear amount

## Usage Examples

### Get Employee Details
```bash
curl -X GET "http://localhost:8000/api/employee/garnishment-details/EE3FEMJN/CLIENT001/"
```

### Update Employee Data
```bash
curl -X PUT "http://localhost:8000/api/employee/garnishment-update/EE3FEMJN/CLIENT001/" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "number_of_exemptions": 3,
    "marital_status": "Married"
  }'
```

### List Employees with Search
```bash
curl -X GET "http://localhost:8000/api/employee/garnishment-list/?search=John&page=1&page_size=5"
```

## Notes

1. All APIs use case-insensitive matching for ee_id and client_id
2. The update API supports partial updates - only provided fields will be updated
3. Essential employee information with garnishment details is returned (no payroll data)
4. All APIs include proper error handling and validation
5. The list API supports pagination and search functionality
6. All responses follow a consistent format with success/error indicators
7. Garnishment data structure includes all garnishment orders for the employee grouped by type
8. Both ee_id and client_id are required in URL path for detail and update operations
9. Payroll-related fields (gross_pay, wages, payroll_taxes, etc.) are excluded from responses
10. Employee is filtered by both ee_id and client_id, garnishment orders are filtered by ee_id
