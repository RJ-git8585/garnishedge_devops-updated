import logging
import sys
import os
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ProcessorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "processor"

    def ready(self):
        """
        Initialize scheduler when Django starts.
        This prevents the scheduler from running during migrations or tests.
        """
        # Only start scheduler in the main process (not during migrations or tests)
        # Check if we're running migrations, tests, or collectstatic
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        if 'test' in sys.argv or 'TESTING' in os.environ:
            return
        if 'collectstatic' in sys.argv:
            return
        
        # In development with runserver, only start scheduler in the main process
        # In production, RUN_MAIN might not be set, so we check if we're in the reloader
        if 'runserver' in sys.argv:
            if os.environ.get('RUN_MAIN') != 'true':
                return
        
        try:
            from processor.scheduler import start_scheduler
            start_scheduler()
        except Exception as e:
            logger.exception(f"Error starting scheduler: {e}")
