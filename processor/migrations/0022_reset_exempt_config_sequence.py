# Generated manually to reset sequence after manual ID insertions

from django.db import migrations


def reset_sequence(apps, schema_editor):
    """
    Reset the PostgreSQL sequence for exempt_config.id to start from
    the maximum existing ID + 1.
    
    This fixes the issue where manually inserted records with explicit IDs
    don't update the sequence, causing duplicate key errors on new inserts.
    """
    with schema_editor.connection.cursor() as cursor:
        # Get the maximum ID from the table
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM exempt_config;")
        max_id = cursor.fetchone()[0]
        
        if max_id > 0:
            # Find the actual sequence name for the id column
            # PostgreSQL returns the sequence name with schema (e.g., 'public.exempt_config_id_seq')
            cursor.execute("""
                SELECT pg_get_serial_sequence('exempt_config', 'id');
            """)
            result = cursor.fetchone()
            
            if result and result[0]:
                sequence_name = result[0]
                
                # Set the sequence to start from max_id + 1
                # The 'false' parameter means the next value will be max_id + 1
                # Use the sequence name as-is (with schema) or quote it properly
                cursor.execute(
                    f"SELECT setval('{sequence_name}', %s, false);",
                    [max_id]
                )
                print(f"Reset sequence '{sequence_name}' to start from {max_id + 1}")
            else:
                # Fallback: try the standard naming convention
                cursor.execute(
                    "SELECT setval('exempt_config_id_seq', %s, false);",
                    [max_id]
                )
                print(f"Reset sequence 'exempt_config_id_seq' to start from {max_id + 1}")


def reverse_reset_sequence(apps, schema_editor):
    """
    Reverse operation - not really needed, but included for completeness
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("processor", "0021_add_effective_date_to_exemptconfig"),
    ]

    operations = [
        migrations.RunPython(reset_sequence, reverse_reset_sequence),
    ]

