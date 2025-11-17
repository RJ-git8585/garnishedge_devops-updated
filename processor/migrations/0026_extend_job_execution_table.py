from django.db import migrations


def add_columns_to_job_execution(apps, schema_editor):
    table_name = "django_apscheduler_djangojobexecution"
    connection = schema_editor.connection
    introspection = connection.introspection

    with connection.cursor() as cursor:
        existing_columns = {col.name for col in introspection.get_table_description(cursor, table_name)}

    statements = []
    quoted_table = schema_editor.quote_name(table_name)

    if "table_name" not in existing_columns:
        statements.append(f"ALTER TABLE {quoted_table} ADD COLUMN table_name varchar(255) NULL")

    if "activate_id" not in existing_columns:
        statements.append(f"ALTER TABLE {quoted_table} ADD COLUMN activate_id integer NULL")

    if "deactivate_id" not in existing_columns:
        statements.append(f"ALTER TABLE {quoted_table} ADD COLUMN deactivate_id integer NULL")

    for sql in statements:
        schema_editor.execute(sql)


def remove_columns_from_job_execution(apps, schema_editor):
    """
    Reverse migration left intentionally as a no-op to avoid dropping data.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("processor", "0025_garnishmentfeesrules_effective_date"),
    ]

    operations = [
        migrations.RunPython(add_columns_to_job_execution, remove_columns_from_job_execution),
    ]







