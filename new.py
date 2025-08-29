import json
from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = "Fix fixture model identifiers based on db_table -> model mapping"

    def add_arguments(self, parser):
        parser.add_argument("input_file", type=str, help="Path to original fixture JSON")
        parser.add_argument("output_file", type=str, help="Path to save fixed fixture JSON")

    def handle(self, *args, **options):
        input_file = options["input_file"]
        output_file = options["output_file"]

        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        fixed = []

        # Build map: db_table -> model_identifier
        table_to_model = {}
        for model in apps.get_models():
            db_table = model._meta.db_table
            app_label = model._meta.app_label
            model_name = model.__name__.lower()
            table_to_model[db_table] = f"{app_label}.{model_name}"

        self.stdout.write(self.style.SUCCESS(f"Built mapping for {len(table_to_model)} models."))

        for obj in data:
            model_id = obj["model"]

            try:
                # Does this model id already exist?
                apps.get_model(*model_id.split("."))
                fixed.append(obj)
            except LookupError:
                old_table = model_id.split(".")[-1]
                if old_table in table_to_model:
                    new_model_id = table_to_model[old_table]
                    self.stdout.write(f"⚡ Rewriting {model_id} -> {new_model_id}")
                    obj["model"] = new_model_id
                else:
                    self.stdout.write(self.style.WARNING(f"❌ Could not map {model_id}, leaving as is"))
                fixed.append(obj)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(fixed, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"✅ Fixed fixture written to {output_file}"))
