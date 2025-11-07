"""
Management command to update is_active status based on effective_date.

This command is automatically scheduled to run daily at 2:00 AM via APScheduler.
You can also run it manually:

Usage:
    python manage.py update_effective_dates

The command:
1. Activates configs whose effective_date has arrived
2. Deactivates previous configs when new configs become effective
3. Handles past configs that should have been activated earlier

Processes ExemptConfig, WithholdingLimit, GarnishmentFees, and DeductionPriority models.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from datetime import date
import logging
from processor.models import ExemptConfig, WithholdingLimit, GarnishmentFees, DeductionPriority

logger = logging.getLogger(__name__)

SCHEDULER_JOB_ID = "update_effective_dates_daily"


class Command(BaseCommand):
    help = 'Update is_active status for ExemptConfig, WithholdingLimit, GarnishmentFees, and DeductionPriority based on effective_date'

    def handle(self, *args, **options):
        """
        Main command handler that processes effective dates for all models.
        """
        today = date.today()
        self.stdout.write(f"Processing effective dates for {today}")
        
        try:
            summaries = []

            # Process ExemptConfig
            exempt_summary = self._process_exempt_configs(today)
            summaries.append(exempt_summary)

            # Process WithholdingLimit
            withholding_summary = self._process_withholding_limits(today)
            summaries.append(withholding_summary)

            # Process GarnishmentFees
            fees_summary = self._process_garnishment_fees(today)
            summaries.append(fees_summary)

            # Process DeductionPriority
            priority_summary = self._process_deduction_priorities(today)
            summaries.append(priority_summary)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed processing. "
                    f"ExemptConfig: {exempt_summary['activated_count']} activated. "
                    f"WithholdingLimit: {withholding_summary['activated_count']} activated. "
                    f"GarnishmentFees: {fees_summary['activated_count']} activated. "
                    f"DeductionPriority: {priority_summary['activated_count']} activated."
                )
            )

            self._record_job_execution_summary(summaries)

        except Exception as e:
            logger.exception(f"Error processing effective dates: {e}")
            self.stdout.write(
                self.style.ERROR(f"Error processing effective dates: {str(e)}")
            )
            raise
    
    def _process_exempt_configs(self, today):
        """
        Process ExemptConfig records based on effective_date.
        Returns total count of activated configs.
        """
        self.stdout.write("Processing ExemptConfig records...")
        
        activated_ids = []
        deactivated_ids = []
        today_activated_count = 0

        # Step 1: Activate configs whose effective_date is today
        configs_to_activate = ExemptConfig.objects.filter(
            effective_date=today,
            is_active=False
        )
        
        for config in configs_to_activate:
            # Before activating, check if there are matching active configs to deactivate
            deactivated_ids.extend(self._deactivate_matching_exempt_configs(config, today))
            config.is_active = True
            config.save(update_fields=['is_active', 'updated_at'])
            today_activated_count += 1
            activated_ids.append(config.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated ExemptConfig ID {config.id} (effective_date: {config.effective_date})"
                )
            )
        
        if today_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully activated {today_activated_count} ExemptConfig(s)"
                )
            )
        else:
            self.stdout.write("No ExemptConfig records needed activation today")
        
        # Step 2: Process configs with effective_date <= today that are still inactive
        # This handles cases where the command might not have run on the exact day
        past_configs = ExemptConfig.objects.filter(
            effective_date__lte=today,
            is_active=False
        ).exclude(effective_date__isnull=True)
        
        past_activated_count = 0
        for config in past_configs:
            deactivated_ids.extend(self._deactivate_matching_exempt_configs(config, today))
            config.is_active = True
            config.save(update_fields=['is_active', 'updated_at'])
            past_activated_count += 1
            activated_ids.append(config.id)
            logger.info(f"Activated past ExemptConfig ID {config.id} (effective_date: {config.effective_date})")
        
        if past_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated {past_activated_count} past ExemptConfig(s) that should have been active"
                )
            )
        
        return {
            "table": "ExemptConfig",
            "activated_ids": activated_ids,
            "deactivated_ids": deactivated_ids,
            "activated_count": len(activated_ids),
            "deactivated_count": len(deactivated_ids),
        }
    
    def _process_withholding_limits(self, today):
        """
        Process WithholdingLimit records based on effective_date.
        Returns total count of activated limits.
        """
        self.stdout.write("Processing WithholdingLimit records...")
        
        activated_ids = []
        deactivated_ids = []
        today_activated_count = 0

        # Step 1: Activate limits whose effective_date is today
        limits_to_activate = WithholdingLimit.objects.filter(
            effective_date=today,
            is_active=False
        )
        
        for limit in limits_to_activate:
            # Before activating, check if there are matching active limits to deactivate
            deactivated_ids.extend(self._deactivate_matching_withholding_limits(limit, today))
            limit.is_active = True
            limit.save(update_fields=['is_active', 'updated_at'])
            today_activated_count += 1
            activated_ids.append(limit.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated WithholdingLimit ID {limit.id} (effective_date: {limit.effective_date})"
                )
            )
        
        if today_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully activated {today_activated_count} WithholdingLimit(s)"
                )
            )
        else:
            self.stdout.write("No WithholdingLimit records needed activation today")
        
        # Step 2: Process limits with effective_date <= today that are still inactive
        # This handles cases where the command might not have run on the exact day
        past_limits = WithholdingLimit.objects.filter(
            effective_date__lte=today,
            is_active=False
        ).exclude(effective_date__isnull=True)
        
        past_activated_count = 0
        for limit in past_limits:
            deactivated_ids.extend(self._deactivate_matching_withholding_limits(limit, today))
            limit.is_active = True
            limit.save(update_fields=['is_active', 'updated_at'])
            past_activated_count += 1
            activated_ids.append(limit.id)
            logger.info(f"Activated past WithholdingLimit ID {limit.id} (effective_date: {limit.effective_date})")
        
        if past_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated {past_activated_count} past WithholdingLimit(s) that should have been active"
                )
            )
        
        return {
            "table": "WithholdingLimit",
            "activated_ids": activated_ids,
            "deactivated_ids": deactivated_ids,
            "activated_count": len(activated_ids),
            "deactivated_count": len(deactivated_ids),
        }
    
    def _deactivate_matching_exempt_configs(self, new_config, today):
        """
        Deactivate previous ExemptConfig records that match the same criteria as the new config.
        
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
            
            ids_to_deactivate = list(matching_configs.values_list('id', flat=True))
            if not ids_to_deactivate:
                return []

            deactivated_count = matching_configs.update(is_active=False)
            
            if deactivated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {deactivated_count} previous ExemptConfig(s) for new config ID {new_config.id}"
                    )
                )
                logger.info(
                    f"Deactivated {deactivated_count} previous ExemptConfig(s) when activating config ID {new_config.id}"
                )

            return ids_to_deactivate

        except Exception as e:
            logger.exception(
                f"Error deactivating matching ExemptConfig(s) for config ID {new_config.id}: {e}"
            )
            # Don't fail the command if deactivation fails for one config, just log it
            return []
    
    def _deactivate_matching_withholding_limits(self, new_limit, today):
        """
        Deactivate previous WithholdingLimit records that match the same criteria as the new limit.
        
        Args:
            new_limit: The WithholdingLimit instance being activated
            today: Today's date
        """
        try:
            # Find limits that should be deactivated based on matching criteria
            # Match by key fields: rule, wl, and other identifying fields
            matching_limits = WithholdingLimit.objects.filter(
                rule=new_limit.rule,
                wl=new_limit.wl,
                is_active=True
            ).exclude(id=new_limit.id)
            
            # Match optional fields if they exist in new limit
            if new_limit.supports_2nd_family is not None:
                matching_limits = matching_limits.filter(supports_2nd_family=new_limit.supports_2nd_family)
            else:
                matching_limits = matching_limits.filter(Q(supports_2nd_family__isnull=True))
            
            if new_limit.arrears_of_more_than_12_weeks is not None:
                matching_limits = matching_limits.filter(arrears_of_more_than_12_weeks=new_limit.arrears_of_more_than_12_weeks)
            else:
                matching_limits = matching_limits.filter(Q(arrears_of_more_than_12_weeks__isnull=True))
            
            if new_limit.number_of_orders:
                matching_limits = matching_limits.filter(number_of_orders=new_limit.number_of_orders)
            else:
                matching_limits = matching_limits.filter(Q(number_of_orders__isnull=True) | Q(number_of_orders=''))
            
            if new_limit.weekly_de_code:
                matching_limits = matching_limits.filter(weekly_de_code=new_limit.weekly_de_code)
            else:
                matching_limits = matching_limits.filter(Q(weekly_de_code__isnull=True) | Q(weekly_de_code=''))
            
            if new_limit.work_state:
                matching_limits = matching_limits.filter(work_state=new_limit.work_state)
            else:
                matching_limits = matching_limits.filter(Q(work_state__isnull=True) | Q(work_state=''))
            
            if new_limit.issuing_state:
                matching_limits = matching_limits.filter(issuing_state=new_limit.issuing_state)
            else:
                matching_limits = matching_limits.filter(Q(issuing_state__isnull=True) | Q(issuing_state=''))
            
            # Only deactivate limits that have effective_date in the past or null
            # (Don't deactivate limits with future effective dates)
            matching_limits = matching_limits.filter(
                Q(effective_date__isnull=True) | Q(effective_date__lt=new_limit.effective_date)
            )
            
            ids_to_deactivate = list(matching_limits.values_list('id', flat=True))
            if not ids_to_deactivate:
                return []

            deactivated_count = matching_limits.update(is_active=False)
            
            if deactivated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {deactivated_count} previous WithholdingLimit(s) for new limit ID {new_limit.id}"
                    )
                )
                logger.info(
                    f"Deactivated {deactivated_count} previous WithholdingLimit(s) when activating limit ID {new_limit.id}"
                )

            return ids_to_deactivate

        except Exception as e:
            logger.exception(
                f"Error deactivating matching WithholdingLimit(s) for limit ID {new_limit.id}: {e}"
            )
            # Don't fail the command if deactivation fails for one limit, just log it
            return []
    
    def _process_garnishment_fees(self, today):
        """
        Process GarnishmentFees records based on effective_date.
        Returns total count of activated fees.
        """
        self.stdout.write("Processing GarnishmentFees records...")
        
        activated_ids = []
        deactivated_ids = []
        today_activated_count = 0

        # Step 1: Activate fees whose effective_date is today
        fees_to_activate = GarnishmentFees.objects.filter(
            effective_date=today,
            is_active=False
        )
        
        for fee in fees_to_activate:
            # Before activating, check if there are matching active fees to deactivate
            deactivated_ids.extend(self._deactivate_matching_garnishment_fees(fee, today))
            fee.is_active = True
            fee.save(update_fields=['is_active', 'updated_at'])
            today_activated_count += 1
            activated_ids.append(fee.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated GarnishmentFees ID {fee.id} (effective_date: {fee.effective_date})"
                )
            )
        
        if today_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully activated {today_activated_count} GarnishmentFees record(s)"
                )
            )
        else:
            self.stdout.write("No GarnishmentFees records needed activation today")
        
        # Step 2: Process fees with effective_date <= today that are still inactive
        # This handles cases where the command might not have run on the exact day
        past_fees = GarnishmentFees.objects.filter(
            effective_date__lte=today,
            is_active=False
        ).exclude(effective_date__isnull=True)
        
        past_activated_count = 0
        for fee in past_fees:
            deactivated_ids.extend(self._deactivate_matching_garnishment_fees(fee, today))
            fee.is_active = True
            fee.save(update_fields=['is_active', 'updated_at'])
            past_activated_count += 1
            activated_ids.append(fee.id)
            logger.info(f"Activated past GarnishmentFees ID {fee.id} (effective_date: {fee.effective_date})")
        
        if past_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated {past_activated_count} past GarnishmentFees record(s) that should have been active"
                )
            )
        
        return {
            "table": "GarnishmentFees",
            "activated_ids": activated_ids,
            "deactivated_ids": deactivated_ids,
            "activated_count": len(activated_ids),
            "deactivated_count": len(deactivated_ids),
        }
    
    def _process_deduction_priorities(self, today):
        """
        Process DeductionPriority records based on effective_date.
        Returns total count of activated priorities.
        """
        self.stdout.write("Processing DeductionPriority records...")
        
        activated_ids = []
        deactivated_ids = []
        today_activated_count = 0

        # Step 1: Activate priorities whose effective_date is today
        priorities_to_activate = DeductionPriority.objects.filter(
            effective_date=today,
            is_active=False
        )
        
        for priority in priorities_to_activate:
            # Before activating, check if there are matching active priorities to deactivate
            deactivated_ids.extend(self._deactivate_matching_deduction_priorities(priority, today))
            priority.is_active = True
            priority.save(update_fields=['is_active', 'updated_at'])
            today_activated_count += 1
            activated_ids.append(priority.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated DeductionPriority ID {priority.id} (effective_date: {priority.effective_date})"
                )
            )
        
        if today_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully activated {today_activated_count} DeductionPriority record(s)"
                )
            )
        else:
            self.stdout.write("No DeductionPriority records needed activation today")
        
        # Step 2: Process priorities with effective_date <= today that are still inactive
        # This handles cases where the command might not have run on the exact day
        past_priorities = DeductionPriority.objects.filter(
            effective_date__lte=today,
            is_active=False
        ).exclude(effective_date__isnull=True)
        
        past_activated_count = 0
        for priority in past_priorities:
            deactivated_ids.extend(self._deactivate_matching_deduction_priorities(priority, today))
            priority.is_active = True
            priority.save(update_fields=['is_active', 'updated_at'])
            past_activated_count += 1
            activated_ids.append(priority.id)
            logger.info(f"Activated past DeductionPriority ID {priority.id} (effective_date: {priority.effective_date})")
        
        if past_activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated {past_activated_count} past DeductionPriority record(s) that should have been active"
                )
            )
        
        return {
            "table": "DeductionPriority",
            "activated_ids": activated_ids,
            "deactivated_ids": deactivated_ids,
            "activated_count": len(activated_ids),
            "deactivated_count": len(deactivated_ids),
        }
    
    def _deactivate_matching_garnishment_fees(self, new_fee, today):
        """
        Deactivate previous GarnishmentFees records that match the same criteria as the new fee.
        
        Args:
            new_fee: The GarnishmentFees instance being activated
            today: Today's date
        """
        try:
            # Find fees that should be deactivated based on matching criteria
            # Match by key fields: state, garnishment_type, pay_period, rule
            matching_fees = GarnishmentFees.objects.filter(
                state=new_fee.state,
                garnishment_type=new_fee.garnishment_type,
                pay_period=new_fee.pay_period,
                rule=new_fee.rule,
                is_active=True
            ).exclude(id=new_fee.id)
            
            # Match optional fields if they exist in new fee
            if new_fee.status:
                matching_fees = matching_fees.filter(status=new_fee.status)
            else:
                matching_fees = matching_fees.filter(Q(status__isnull=True) | Q(status=''))
            
            if new_fee.payable_by:
                matching_fees = matching_fees.filter(payable_by=new_fee.payable_by)
            else:
                matching_fees = matching_fees.filter(Q(payable_by__isnull=True) | Q(payable_by=''))
            
            if new_fee.amount:
                matching_fees = matching_fees.filter(amount=new_fee.amount)
            else:
                matching_fees = matching_fees.filter(Q(amount__isnull=True) | Q(amount=''))
            
            # Only deactivate fees that have effective_date in the past or null
            # (Don't deactivate fees with future effective dates)
            matching_fees = matching_fees.filter(
                Q(effective_date__isnull=True) | Q(effective_date__lt=new_fee.effective_date)
            )

            ids_to_deactivate = list(matching_fees.values_list('id', flat=True))
            if not ids_to_deactivate:
                return []

            deactivated_count = matching_fees.update(is_active=False)
            
            if deactivated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {deactivated_count} previous GarnishmentFees record(s) for new fee ID {new_fee.id}"
                    )
                )
                logger.info(
                    f"Deactivated {deactivated_count} previous GarnishmentFees record(s) when activating fee ID {new_fee.id}"
                )

            return ids_to_deactivate

        except Exception as e:
            logger.exception(
                f"Error deactivating matching GarnishmentFees record(s) for fee ID {new_fee.id}: {e}"
            )
            # Don't fail the command if deactivation fails for one fee, just log it
            return []
    
    def _deactivate_matching_deduction_priorities(self, new_priority, today):
        """
        Deactivate previous DeductionPriority records that match the same criteria as the new priority.
        
        Args:
            new_priority: The DeductionPriority instance being activated
            today: Today's date
        """
        try:
            # Find priorities that should be deactivated based on matching criteria
            # Match by key fields: state, deduction_type
            matching_priorities = DeductionPriority.objects.filter(
                state=new_priority.state,
                deduction_type=new_priority.deduction_type,
                is_active=True
            ).exclude(id=new_priority.id)
            
            # Only deactivate priorities that have effective_date in the past or null
            # (Don't deactivate priorities with future effective dates)
            matching_priorities = matching_priorities.filter(
                Q(effective_date__isnull=True) | Q(effective_date__lt=new_priority.effective_date)
            )
            
            ids_to_deactivate = list(matching_priorities.values_list('id', flat=True))
            if not ids_to_deactivate:
                return []

            deactivated_count = matching_priorities.update(is_active=False)
            
            if deactivated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {deactivated_count} previous DeductionPriority record(s) for new priority ID {new_priority.id}"
                    )
                )
                logger.info(
                    f"Deactivated {deactivated_count} previous DeductionPriority record(s) when activating priority ID {new_priority.id}"
                )

            return ids_to_deactivate

        except Exception as e:
            logger.exception(
                f"Error deactivating matching DeductionPriority record(s) for priority ID {new_priority.id}: {e}"
            )
            # Don't fail the command if deactivation fails for one priority, just log it
            return []

    def _record_job_execution_summary(self, summaries):
        """Persist summary data for the most recent scheduler job execution."""
        if not summaries:
            return

        try:
            from django_apscheduler.models import DjangoJobExecution
        except Exception as exc:
            logger.warning("Unable to import DjangoJobExecution to record summary: %s", exc)
            return

        job_execution = (
            DjangoJobExecution.objects.filter(job_id=SCHEDULER_JOB_ID)
            .order_by("-run_time")
            .first()
        )

        if job_execution is None:
            logger.debug(
                "No DjangoJobExecution record found for job_id %s; skipping summary update",
                SCHEDULER_JOB_ID,
            )
            return

        activated_entries = []
        deactivated_entries = []
        tables_seen = []

        for summary in summaries:
            table = summary.get("table")
            activated = summary.get("activated_ids", []) or []
            if activated:
                activated_entries.extend((table, value) for value in activated)
                tables_seen.append(table)

            deactivated = summary.get("deactivated_ids", []) or []
            if deactivated:
                deactivated_entries.extend((table, value) for value in deactivated)
                tables_seen.append(table)

        unique_tables = []
        for table in tables_seen:
            if table and table not in unique_tables:
                unique_tables.append(table)

        table_name_value = ",".join(unique_tables) if unique_tables else None
        activate_id_value = activated_entries[-1][1] if activated_entries else None
        deactivate_id_value = deactivated_entries[-1][1] if deactivated_entries else None

        updates = {}
        if getattr(job_execution, "table_name", None) != table_name_value:
            updates["table_name"] = table_name_value
        if getattr(job_execution, "activate_id", None) != activate_id_value:
            updates["activate_id"] = activate_id_value
        if getattr(job_execution, "deactivate_id", None) != deactivate_id_value:
            updates["deactivate_id"] = deactivate_id_value

        if not updates:
            return

        for field, value in updates.items():
            setattr(job_execution, field, value)

        job_execution.save(update_fields=list(updates.keys()))

