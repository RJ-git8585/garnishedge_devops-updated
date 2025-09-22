# Batch Payroll Processing API

This API processes batch payroll data and enriches it with employee and garnishment information from the database.

## Endpoint

```
POST /batch/payroll/batch/
```

## Request Format

The API accepts a JSON payload with the following structure:

```json
{
  "batch_id": "BATCH001",
  "cases": [
    {
      "client_id": "CL1002",
      "ee_id": "EE2125",
      "pay_period": "Monthly",
      "payroll_date": "2025-09-01",
      "wages": 5000,
      "commission_and_bonus": 500,
      "non_accountable_allowances": 200,
      "gross_pay": 5700,
      "payroll_taxes": {
        "federal_income_tax": 900,
        "state_tax": 150,
        "local_other_taxes": 50,
        "medicare_tax": 75,
        "social_security_tax": 310,
        "wilmington_tax": 20,
        "california_sdi": 40,
        "medical_insurance_pretax": 120,
        "life_insurance": 60,
        "retirement_401k": 200,
        "industrial_insurance": 30,
        "union_dues": 25
      },
      "net_pay": 3770
    }
  ]
}
```

## Response Format

### Successful Response (Employee Found)

```json
{
  "success": true,
  "message": "Batch processing completed",
  "data": {
    "batch_id": "BATCH001",
    "cases": [
      {
        "ee_id": "EE2125",
        "work_state": "Washington",
        "home_state": "Arizona",
        "issuing_state": "alabama",
        "no_of_exemption_including_self": 0,
        "is_multiple_garnishment_type": true,
        "no_of_student_default_loan": 1,
        "pay_period": "Monthly",
        "filing_status": "single",
        "wages": 5000,
        "commission_and_bonus": 500,
        "non_accountable_allowances": 200,
        "gross_pay": 5700,
        "payroll_taxes": {
          "federal_income_tax": 900,
          "state_tax": 150,
          "local_other_taxes": 50,
          "medicare_tax": 75,
          "social_security_tax": 310,
          "wilmington_tax": 20,
          "california_sdi": 40,
          "medical_insurance_pretax": 120,
          "life_insurance": 60,
          "retirement_401k": 200,
          "industrial_insurance": 30,
          "union_dues": 25
        },
        "net_pay": 3770,
        "is_blind": false,
        "statement_of_exemption_received_date": "05-03-2025",
        "garn_start_date": "11-12-2025",
        "non_consumer_debt": false,
        "consumer_debt": false,
        "age": 38,
        "spouse_age": 38,
        "is_spouse_blind": false,
        "support_second_family": false,
        "no_of_dependent_child": 0,
        "arrear_greater_than_12_weeks": false,
        "ftb_type": null,
        "garnishment_data": [
          {
            "type": "child_support",
            "data": [
              {
                "case_id": "C129090",
                "ordered_amount": 100,
                "arrear_amount": 20
              }
            ]
          }
        ],
        "garnishment_orders": [
          "child_support"
        ]
      }
    ]
  },
  "status_code": 200
}
```

### Response with Missing Employees

```json
{
  "success": true,
  "message": "Batch processing completed",
  "data": {
    "batch_id": "BATCH001",
    "cases": [
      {
        "ee_id": "EE2125",
        "work_state": "Washington",
        "home_state": "Arizona",
        // ... other enriched fields
      }
    ],
    "not_found_employees": [
      {
        "not_found": "EE3423",
        "message": "ee_id EE3423 is not found in the records"
      }
    ]
  },
  "status_code": 200
}
```

### Error Response (All Employees Not Found)

```json
{
  "success": false,
  "message": "No employees found",
  "error": {
    "not_found": "EE3423",
    "message": "ee_id EE3423 is not found in the records"
  },
  "status_code": 400
}
```

## Processing Logic

1. **Employee Lookup**: For each case, the API looks up the employee using the `ee_id` in the `EmployeeDetail` model.

2. **Data Enrichment**: If the employee is found, the API enriches the case with:
   - Employee details (age, states, exemptions, etc.)
   - Garnishment orders and their details
   - Filing status and other employee-specific information

3. **Garnishment Data**: The API groups garnishment orders by type and includes:
   - Case ID
   - Ordered amount
   - Arrear amount

4. **Error Handling**: If an employee is not found, the API logs the missing record and continues processing other employees.

## Database Models Used

- **EmployeeDetail**: Contains employee information
- **GarnishmentOrder**: Contains garnishment order details
- **State**: Contains state information
- **GarnishmentType**: Contains garnishment type information
- **FedFilingStatus**: Contains federal filing status information

## Testing

Use the provided test script to test the API:

```bash
python test_batch_api.py
```

Make sure the Django server is running on `localhost:8000` before running the test.

## API Documentation

The API is documented using Swagger/OpenAPI. You can access the interactive documentation at:

- Swagger UI: `http://localhost:8000/api/docs/swagger/`
- ReDoc: `http://localhost:8000/api/docs/redoc/`

## Error Codes

- **200**: Success - Batch processing completed
- **400**: Bad Request - Invalid input data or no employees found
- **500**: Internal Server Error - Server error during processing
