"""
Scheduler configuration for periodic tasks.

This module sets up APScheduler to run management commands on a schedule.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")


@util.close_old_connections
def update_effective_dates_job():
    """
    Job function to run the update_effective_dates management command.
    """
    from django.core.management import call_command
    
    try:
        logger.info("Starting scheduled update_effective_dates command")
        call_command('update_effective_dates')
        logger.info("Completed scheduled update_effective_dates command")
    except Exception as e:
        logger.exception(f"Error running update_effective_dates command: {e}")


def start_scheduler():
    """
    Start the scheduler and add scheduled jobs.
    This should be called from AppConfig.ready()
    """
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return
    
    try:
        # Schedule the update_effective_dates command to run daily at 2:00 AM
        scheduler.add_job(
            update_effective_dates_job,
            trigger=CronTrigger(hour=2, minute=0),  # Run daily at 2:00 AM
            id="update_effective_dates_daily",
            name="Update Effective Dates Daily",
            replace_existing=True,
            max_instances=1,
        )
        
        # Register Django events to clean up old job executions
        register_events(scheduler)
        
        scheduler.start()
        logger.info("Scheduler started successfully")
        logger.info("Scheduled update_effective_dates to run daily at 2:00 AM")
        
    except Exception as e:
        logger.exception(f"Error starting scheduler: {e}")


def shutdown_scheduler():
    """
    Shutdown the scheduler gracefully.
    Call this when Django is shutting down.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

