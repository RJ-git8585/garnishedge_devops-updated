from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("user_app", "0047_achgarnishmentconfig"),
    ]

    operations = [
        migrations.RenameField(
            model_name="payeedetails",
            old_name="payee_id",
            new_name="id",
        ),
    ]


