"""
Management command to update is_active status based on effective_date.

This command should be run daily (e.g., via cron or scheduled task) to:
1. Activate configs whose effective_date has arrived
2. Deactivate previous configs when new configs become effective

Usage:
    python manage.py update_effective_dates
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from datetime import date
import logging
from processor.models import ExemptConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update is_active status for ExemptConfig based on effective_date'

    def handle(self, *args, **options):
        """
        Main command handler that processes effective dates.
        """
        today = date.today()
        self.stdout.write(f"Processing effective dates for {today}")
        
        try:
            # Step 1: Activate configs whose effective_date is today
            configs_to_activate = ExemptConfig.objects.filter(
                effective_date=today,
                is_active=False
            )
            
            activated_count = 0
            for config in configs_to_activate:
                # Before activating, check if there are matching active configs to deactivate
                self._deactivate_matching_configs(config, today)
                config.is_active = True
                config.save(update_fields=['is_active', 'updated_at'])
                activated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Activated config ID {config.id} (effective_date: {config.effective_date})"
                    )
                )
            
            if activated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully activated {activated_count} config(s)"
                    )
                )
            else:
                self.stdout.write("No configs needed activation today")
            
            # Step 2: Process configs with effective_date <= today that are still inactive
            # This handles cases where the command might not have run on the exact day
            past_configs = ExemptConfig.objects.filter(
                effective_date__lte=today,
                is_active=False
            ).exclude(effective_date__isnull=True)
            
            past_activated_count = 0
            for config in past_configs:
                self._deactivate_matching_configs(config, today)
                config.is_active = True
                config.save(update_fields=['is_active', 'updated_at'])
                past_activated_count += 1
                logger.info(f"Activated past config ID {config.id} (effective_date: {config.effective_date})")
            
            if past_activated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Activated {past_activated_count} past config(s) that should have been active"
                    )
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed processing. Total activated: {activated_count + past_activated_count}"
                )
            )
            
        except Exception as e:
            logger.exception(f"Error processing effective dates: {e}")
            self.stdout.write(
                self.style.ERROR(f"Error processing effective dates: {str(e)}")
            )
            raise
    
    def _deactivate_matching_configs(self, new_config, today):
        """
        Deactivate previous configs that match the same criteria as the new config.
        
        Args:
            new_config: The ExemptConfig instance being activated
            today: Today's date
        """
        try:
            # Find configs that should be deactivated based on matching criteria
            # Match by key fields: state, pay_period, garnishment_type
            matching_configs = ExemptConfig.objects.filter(
                state=new_config.state,
                pay_period=new_config.pay_period,
                garnishment_type=new_config.garnishment_type,
                is_active=True
            ).exclude(id=new_config.id)
            
            # Match optional fields if they exist in new config
            if new_config.debt_type:
                matching_configs = matching_configs.filter(debt_type=new_config.debt_type)
            else:
                # If new config doesn't have debt_type, only match configs without debt_type
                matching_configs = matching_configs.filter(Q(debt_type__isnull=True) | Q(debt_type=''))
            
            if new_config.home_state:
                matching_configs = matching_configs.filter(home_state=new_config.home_state)
            else:
                matching_configs = matching_configs.filter(Q(home_state__isnull=True) | Q(home_state=''))
            
            if new_config.ftb_type:
                matching_configs = matching_configs.filter(ftb_type=new_config.ftb_type)
            else:
                matching_configs = matching_configs.filter(Q(ftb_type__isnull=True) | Q(ftb_type=''))
            
            # Only deactivate configs that have effective_date in the past or null
            # (Don't deactivate configs with future effective dates)
            matching_configs = matching_configs.filter(
                Q(effective_date__isnull=True) | Q(effective_date__lt=new_config.effective_date)
            )
            
            deactivated_count = matching_configs.update(is_active=False)
            
            if deactivated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {deactivated_count} previous config(s) for new config ID {new_config.id}"
                    )
                )
                logger.info(
                    f"Deactivated {deactivated_count} previous config(s) when activating config ID {new_config.id}"
                )
        
        except Exception as e:
            logger.exception(
                f"Error deactivating matching configs for config ID {new_config.id}: {e}"
            )
            # Don't fail the command if deactivation fails for one config, just log it

