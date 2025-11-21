# CDC API Setup Checklist

This checklist outlines all the changes you need to make to get the CDC API working in production.

## ✅ Code Changes (Already Done)

The following are already implemented:
- ✅ API View (`user_app/views/change_log_views.py`)
- ✅ Serializer (`user_app/serializers/change_log_serializers.py`)
- ✅ URL routing (`user_app/urls/log_urls.py` and `garnishedge_project/urls.py`)
- ✅ Required packages in `requirements.txt` (pyodbc, django-mssql-backend)

---

## 🔧 Changes You Need to Make

### 1. **Configure Database Connection for Production**

**File:** `garnishedge_project/settings.py`

**Current State:** Using `dj_database_url` (line 158-162)

**Action Required:** In production, ensure your `DATABASE_URL` environment variable points to Azure SQL, OR uncomment and configure the Azure SQL block.

**Option A: Using DATABASE_URL (Recommended)**
```bash
# Set environment variable in production
DATABASE_URL=mssql://username:password@hostname:1433/database?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

**Option B: Uncomment Azure SQL Config Block**
```python
# In settings.py, uncomment lines 165-179 and set environment variables:
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': env('AZURE_DB_NAME'),
        'USER': env('AZURE_DB_USER'),
        'PASSWORD': env('AZURE_DB_PASSWORD'),
        'HOST': env('AZURE_DB_HOST'),
        'PORT': env('AZURE_DB_PORT'),
        'OPTIONS': {
            'driver': env('AZURE_DB_DRIVER'),  # e.g., 'ODBC Driver 18 for SQL Server'
            'Encrypt': 'yes',
            'TrustServerCertificate': 'no',
        }
    }
}
```

**Required Environment Variables:**
- `AZURE_DB_NAME` - Your Azure SQL database name
- `AZURE_DB_USER` - Database username
- `AZURE_DB_PASSWORD` - Database password
- `AZURE_DB_HOST` - Azure SQL server hostname (e.g., `yourserver.database.windows.net`)
- `AZURE_DB_PORT` - Port (usually `1433`)
- `AZURE_DB_DRIVER` - ODBC driver name (e.g., `ODBC Driver 18 for SQL Server`)

---

### 2. **Enable CDC on Azure SQL Database**

**Action Required:** Run these SQL commands on your Azure SQL Database.

#### Step 2.1: Enable CDC on Database
```sql
-- Connect to your Azure SQL Database and run:
EXEC sys.sp_cdc_enable_db;
```

#### Step 2.2: Enable CDC on Each Table You Want to Track

For each table you want to audit, run:

```sql
-- Example for GarnishmentOrder table
EXEC sys.sp_cdc_enable_table
    @source_schema = N'dbo',
    @source_name = N'GarnishmentOrder',
    @role_name = N'cdc_admin',  -- Optional: role for CDC access
    @capture_instance = N'dbo_GarnishmentOrder';  -- This name is important!

-- Example for Employee table
EXEC sys.sp_cdc_enable_table
    @source_schema = N'dbo',
    @source_name = N'Employee',
    @role_name = N'cdc_admin',
    @capture_instance = N'dbo_Employee';

-- Add more tables as needed...
```

**Important Notes:**
- The `@capture_instance` name must match what you configure in `CDC_CAPTURE_INSTANCES`
- Your tables must have a `modified_by` column (or your custom user tracking column)
- CDC will automatically create system tables under the `cdc` schema

#### Step 2.3: Verify CDC is Enabled
```sql
-- Check if CDC is enabled on database
SELECT is_cdc_enabled FROM sys.databases WHERE name = 'YourDatabaseName';

-- List all CDC capture instances
SELECT * FROM cdc.change_tables;

-- View recent changes (example)
SELECT TOP 10 * FROM cdc.dbo_GarnishmentOrder_CT ORDER BY __$start_lsn DESC;
```

---

### 3. **Configure CDC_CAPTURE_INSTANCES**

**File:** Environment variable or `.env` file

**Action Required:** Set the `CDC_CAPTURE_INSTANCES` environment variable with JSON configuration.

**Format:**
```json
{
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
  }
}
```

**Where to Set:**

**Option A: Environment Variable (Production)**
```bash
export CDC_CAPTURE_INSTANCES='{"garnishment_order":{"capture_instance":"dbo_GarnishmentOrder","table_name":"dbo.GarnishmentOrder","user_column":"modified_by","select_columns":["order_number","employee_id","status"]}}'
```

**Option B: .env File (Local Development)**
```env
CDC_CAPTURE_INSTANCES={"garnishment_order":{"capture_instance":"dbo_GarnishmentOrder","table_name":"dbo.GarnishmentOrder","user_column":"modified_by","select_columns":["order_number","employee_id","status"]}}
```

**Option C: Docker/Container Environment**
Add to your `docker-compose.yml` or container environment:
```yaml
environment:
  - CDC_CAPTURE_INSTANCES={"garnishment_order":{"capture_instance":"dbo_GarnishmentOrder","table_name":"dbo.GarnishmentOrder","user_column":"modified_by","select_columns":["order_number","employee_id","status"]}}
```

**Configuration Fields Explained:**
- **`capture_instance`**: Must match the `@capture_instance` from Step 2.2
- **`table_name`**: Display name (can be different from capture_instance)
- **`user_column`**: Column that stores user ID (default: `"modified_by"`)
- **`select_columns`**: Additional columns to include in API response

---

### 4. **Verify Database User Permissions**

**Action Required:** Ensure your database user has permissions to:
- Read from CDC system tables
- Execute CDC functions
- Access the base tables

**SQL Commands:**
```sql
-- Grant CDC read permissions (if using a role)
ALTER ROLE cdc_admin ADD MEMBER your_database_user;

-- Or grant directly to user
GRANT SELECT ON SCHEMA::cdc TO your_database_user;
GRANT VIEW DATABASE STATE TO your_database_user;
```

---

### 5. **Test the API**

**Action Required:** Test the endpoint after deployment.

#### Test 1: Check API is Accessible
```bash
# Get JWT token first
curl -X POST "https://your-api.com/api/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'

# Test CDC endpoint (replace TOKEN and USER_ID)
curl -X GET "https://your-api.com/log/cdc/42/?source=all&limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

#### Test 2: Verify Response
Expected response structure:
```json
{
  "count": 10,
  "source": "all",
  "user_id": 42,
  "results": [
    {
      "table": "dbo.GarnishmentOrder",
      "source_key": "garnishment_order",
      "changed_at": "2024-01-15T10:30:00",
      "operation": "update_after",
      "modified_by": 42,
      "start_lsn": "...",
      "sequence_value": "...",
      "payload": {...}
    }
  ]
}
```

---

## 📋 Quick Setup Summary

1. ✅ **Database Connection**: Configure `DATABASE_URL` or Azure SQL settings
2. ✅ **Enable CDC**: Run `EXEC sys.sp_cdc_enable_db;` and enable on tables
3. ✅ **Set Environment Variable**: Configure `CDC_CAPTURE_INSTANCES` JSON
4. ✅ **Permissions**: Grant CDC read permissions to database user
5. ✅ **Test**: Verify API endpoint works

---

## 🚨 Common Issues & Solutions

### Issue: "The CDC log endpoint requires an Azure SQL / SQL Server backend"
**Solution:** Check that `DATABASES['default']` points to Azure SQL, not PostgreSQL.

### Issue: "No CDC capture instances configured"
**Solution:** Set the `CDC_CAPTURE_INSTANCES` environment variable.

### Issue: "Unable to read CDC logs: Invalid capture instance"
**Solution:** 
- Verify CDC is enabled: `SELECT * FROM cdc.change_tables;`
- Check capture instance name matches exactly (case-sensitive)
- Ensure user has CDC permissions

### Issue: No results returned
**Solution:**
- Verify CDC is capturing: `SELECT COUNT(*) FROM cdc.dbo_GarnishmentOrder_CT;`
- Check if `user_id` exists in `modified_by` column
- Verify time range is within CDC retention period

---

## 📝 Production Deployment Checklist

Before deploying to production:

- [ ] Database connection configured for Azure SQL
- [ ] CDC enabled on database (`EXEC sys.sp_cdc_enable_db;`)
- [ ] CDC enabled on all tables you want to track
- [ ] `CDC_CAPTURE_INSTANCES` environment variable set
- [ ] Database user has CDC read permissions
- [ ] API endpoint tested and working
- [ ] JWT authentication working
- [ ] Error handling verified
- [ ] Logging/monitoring in place

---

## 🔗 Related Files

- API View: `user_app/views/change_log_views.py`
- Serializer: `user_app/serializers/change_log_serializers.py`
- URLs: `user_app/urls/log_urls.py`
- Settings: `garnishedge_project/settings.py` (lines 181-203)
- Documentation: `CDC_API_DOCUMENTATION.md`

---

## 📞 Need Help?

If you encounter issues:
1. Check the troubleshooting section in `CDC_API_DOCUMENTATION.md`
2. Verify SQL setup using the verification queries
3. Check Django logs for detailed error messages
4. Ensure all environment variables are set correctly

