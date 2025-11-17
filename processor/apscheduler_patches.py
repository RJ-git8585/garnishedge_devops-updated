"""Runtime patches for django-apscheduler models."""

import logging
from django.db import models

logger = logging.getLogger(__name__)


def ensure_custom_job_execution_fields():
    """Add custom fields to DjangoJobExecution if they are missing."""
    try:
        from django_apscheduler.models import DjangoJobExecution
    except Exception as exc:
        logger.warning("Unable to import DjangoJobExecution for patching: %s", exc)
        return

    field_factories = {
        "table_name": lambda: models.CharField(max_length=255, null=True, blank=True),
        "activate_id": lambda: models.IntegerField(null=True, blank=True),
        "deactivate_id": lambda: models.IntegerField(null=True, blank=True),
    }

    existing_field_names = {field.name for field in DjangoJobExecution._meta.get_fields()}

    for field_name, factory in field_factories.items():
        if field_name in existing_field_names:
            continue

        field = factory()
        field.set_attributes_from_name(field_name)
        field.contribute_to_class(DjangoJobExecution, field_name)
        logger.debug("Added custom field '%s' to DjangoJobExecution at runtime", field_name)







