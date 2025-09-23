# Integrated Batch Payroll Processing API

The `PostCalculationView` has been enhanced to handle both the original enriched input format and the new payroll input format. This eliminates the need for a separate batch processing API.

## Endpoint

```
POST /garnishment/calculation/
```

## Input Formats

The API now supports two input formats:

### 1. New Payroll Input Format (Recommended)

This format accepts basic payroll data and automatically enriches it with employee and garnishment information from the database.

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

### 2. Original Enriched Input Format (Legacy Support)

This format includes all employee and garnishment information in the input.

```json
{
  "batch_id": "BK7GUXE",
  "cases": [
    {
      "ee_id": "EE123679",
      "work_state": "Washington",
      "home_state": "Arizona",
      "issuing_state": "alabama",
      "no_of_exemption_including_self": 0,
      "is_multiple_garnishment_type": true,
      "no_of_student_default_loan": 1,
      "pay_period": "Weekly",
      "filing_status": "single",
      "wages": 750,
      "commission_and_bonus": 0,
      "non_accountable_allowances": 0,
      "gross_pay": 750,
      "payroll_taxes": {
        "federal_income_tax": 150,
        "social_security_tax": 15,
        "medicare_tax": 12,
        "state_tax": 0,
        "local_tax": 0,
        "union_dues": 0,
        "wilmington_tax": 0,
        "medical_insurance_pretax": 0,
        "industrial_insurance": 0,
        "life_insurance": 0,
        "california_sdi": 0,
        "famli_tax": 0
      },
      "net_pay": 573,
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
      "arrears_greater_than_12_weeks": false,
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
        "child_support",
        "student_default_loan"
      ]
    }
  ]
}
```

## Processing Logic

### For New Payroll Input Format:

1. **Input Detection**: The API detects the new format by checking for `client_id` and `payroll_date` fields
2. **Employee Lookup**: For each case, looks up the employee using `ee_id` in the `EmployeeDetail` model
3. **Data Enrichment**: Merges employee and garnishment data into the case
4. **Garnishment Processing**: Groups garnishment orders by type with case details
5. **Calculation**: Proceeds with the standard garnishment calculation process

### For Original Enriched Input Format:

1. **Direct Processing**: Uses the input data as-is for garnishment calculations
2. **No Database Lookup**: Assumes all required data is already present

## Response Format

### Successful Response

```json
{
  "success": true,
  "message": "Batch processed successfully.",
  "status_code": 200,
  "batch_id": "BATCH001",
  "processed_at": "2025-01-27T10:30:00.000Z",
  "summary": {
    "total_cases": 2,
    "successful_cases": 2,
    "failed_cases": 0,
    "garnishment_types_processed": ["child_support", "student_default_loan"],
    "missing_employees": 0
  },
  "results": [
    {
      "employee_id": "EE2125",
      "garnishment_calculations": {
        "child_support": {
          "withholding_amount": 150.00,
          "garnishment_fees": 5.00
        }
      }
    }
  ]
}
```

### Response with Missing Employees (Payroll Input Format)

```json
{
  "success": true,
  "message": "Batch processed successfully.",
  "status_code": 200,
  "batch_id": "BATCH001",
  "processed_at": "2025-01-27T10:30:00.000Z",
  "summary": {
    "total_cases": 2,
    "successful_cases": 1,
    "failed_cases": 0,
    "garnishment_types_processed": ["child_support"],
    "missing_employees": 1
  },
  "not_found_employees": [
    {
      "not_found": "EE9999",
      "message": "ee_id EE9999 is not found in the records"
    }
  ],
  "results": [
    {
      "employee_id": "EE2125",
      "garnishment_calculations": {
        "child_support": {
          "withholding_amount": 150.00,
          "garnishment_fees": 5.00
        }
      }
    }
  ]
}
```

## Key Features

✅ **Dual Format Support** - Handles both new payroll and legacy enriched input formats  
✅ **Automatic Data Enrichment** - Enriches payroll data with employee and garnishment information  
✅ **Employee Validation** - Validates employee existence and handles missing employees gracefully  
✅ **Backward Compatibility** - Maintains support for existing enriched input format  
✅ **Error Handling** - Comprehensive error handling for both input formats  
✅ **Performance Optimized** - Uses database prefetching and parallel processing  
✅ **Detailed Logging** - Comprehensive logging for debugging and monitoring  

## Database Models Used

- **EmployeeDetail**: Contains employee information
- **GarnishmentOrder**: Contains garnishment order details
- **State**: Contains state information
- **GarnishmentType**: Contains garnishment type information
- **FedFilingStatus**: Contains federal filing status information

## Migration Guide

### From Separate Batch API

If you were using the separate `BatchPayrollProcessingAPI`:

1. **Update Endpoint**: Change from `/batch/payroll/batch/` to `/garnishment/calculation/`
2. **Input Format**: No changes needed - the same payroll input format is supported
3. **Response Format**: The response now includes garnishment calculation results in addition to enriched data

### From Original Calculation API

If you were using the original calculation API with enriched input:

1. **No Changes Required**: The original enriched input format continues to work
2. **Optional Migration**: You can migrate to the new payroll input format for simplified data submission

## Error Handling

- **400 Bad Request**: Invalid input data or missing required fields
- **400 Bad Request**: All employees not found (payroll input format)
- **500 Internal Server Error**: Server error during processing

## Performance Considerations

- **Database Optimization**: Uses `select_related` and `prefetch_related` for efficient queries
- **Parallel Processing**: Processes multiple cases concurrently using ThreadPoolExecutor
- **Memory Efficient**: Processes cases in batches to avoid memory issues
- **Caching**: Configuration data is preloaded and cached for better performance

## Testing

The API can be tested with both input formats:

```bash
# Test with new payroll input format
curl -X POST http://localhost:8000/garnishment/calculation/ \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "TEST001",
    "cases": [
      {
        "client_id": "CL1001",
        "ee_id": "EE1234",
        "pay_period": "Monthly",
        "payroll_date": "2025-01-01",
        "wages": 5000,
        "gross_pay": 5000,
        "net_pay": 4000,
        "payroll_taxes": {
          "federal_income_tax": 500,
          "state_tax": 200,
          "social_security_tax": 310,
          "medicare_tax": 75
        }
      }
    ]
  }'
```

## API Documentation

The API is documented using Swagger/OpenAPI. Access the interactive documentation at:

- Swagger UI: `http://localhost:8000/api/docs/swagger/`
- ReDoc: `http://localhost:8000/api/docs/redoc/`

