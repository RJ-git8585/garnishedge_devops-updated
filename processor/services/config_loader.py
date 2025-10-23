"""
Configuration loading service for garnishment calculations.
Handles loading and caching of configuration data for different garnishment types.
"""

import logging
from typing import Dict, Set, Any
from processor.models import (
    StateTaxLevyExemptAmtConfig, ExemptConfig, ThresholdAmount,
    AddExemptions, StdExemptions, GarnishmentFees
)
from processor.serializers import (
    ThresholdAmountSerializer, AddExemptionSerializer, StdExemptionSerializer,
    GarnishmentFeesSerializer, StateTaxLevyExemptAmtConfigSerializers
)
from user_app.constants import GarnishmentTypeFields as GT, ConfigDataKeys as CDK

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Service class for loading and managing configuration data for garnishment calculations.
    """

    def preload_config_data(self, garnishment_types: Set[str]) -> Dict[str, Any]:
        """
        Preloads configuration data for the requested garnishment types.
        Enhanced with better error handling and logging.
        """
        config_data = {}
        loaded_types = []
        
        try:
            if GT.STATE_TAX_LEVY in garnishment_types:
                config_data[GT.STATE_TAX_LEVY] = self._load_state_tax_levy_config()
                if config_data[GT.STATE_TAX_LEVY]:
                    loaded_types.append(GT.STATE_TAX_LEVY)

            if GT.CREDITOR_DEBT in garnishment_types:
                config_data[GT.CREDITOR_DEBT] = self._load_creditor_debt_config()
                if config_data[GT.CREDITOR_DEBT]:
                    loaded_types.append(GT.CREDITOR_DEBT)

            if GT.FEDERAL_TAX_LEVY in garnishment_types:
                config_data[GT.FEDERAL_TAX_LEVY] = self._load_federal_tax_config()
                if config_data[GT.FEDERAL_TAX_LEVY]:
                    loaded_types.append(GT.FEDERAL_TAX_LEVY)

            if GT.CHILD_SUPPORT in garnishment_types:
                # Child support config loading is currently disabled
                pass

            if GT.BANKRUPTCY in garnishment_types:
                config_data["bankruptcy"] = self._load_bankruptcy_config()
                if config_data["bankruptcy"]:
                    loaded_types.append("bankruptcy")

            # Load FTB related types
            for type_name, type_id in GT.FTB_RELATED_TYPES.items():
                if type_name in garnishment_types:
                    config_data[type_name] = self._load_ftb_config(type_id)
                    if config_data[type_name]:
                        loaded_types.append(type_name)
            
        except Exception as e:
            logger.error(f"Critical error preloading config data: {e}", exc_info=True) 
        
        return config_data

    def _load_state_tax_levy_config(self) -> list:
        """Load state tax levy configuration data."""
        try:
            queryset = StateTaxLevyExemptAmtConfig.objects.select_related('state').all()
            serializer = StateTaxLevyExemptAmtConfigSerializers(queryset, many=True)
            logger.info(f"Successfully loaded {GT.STATE_TAX_LEVY} config")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading {GT.STATE_TAX_LEVY} config: {e}")
            return []

    def _load_creditor_debt_config(self) -> list:
        """Load creditor debt configuration data."""
        try:
            queryset = ExemptConfig.objects.select_related('state','pay_period','garnishment_type').filter(garnishment_type=5)
            config_ids = queryset.values_list("id", flat=True)
            threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)
            serializer = ThresholdAmountSerializer(threshold_qs, many=True)
            logger.info(f"Successfully loaded {GT.CREDITOR_DEBT} config")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading {GT.CREDITOR_DEBT} config: {e}")
            return []

    def _load_federal_tax_config(self) -> list:
        """Load federal tax levy configuration data."""
        try:
            # Get standard exemptions
            std_exempt = StdExemptions.objects.select_related('year', 'fs', 'pp').all()
            std_serializer = StdExemptionSerializer(std_exempt, many=True)
            logger.info(f"Successfully loaded {GT.FEDERAL_TAX_LEVY} config")
            return std_serializer.data
        except Exception as e:
            logger.error(f"Error loading {GT.FEDERAL_TAX_LEVY} config: {e}")
            return []

    def _load_bankruptcy_config(self) -> list:
        """Load bankruptcy configuration data."""
        try:
            queryset = ExemptConfig.objects.select_related('state','pay_period','garnishment_type').filter(garnishment_type=7)
            config_ids = queryset.values_list("id", flat=True)
            threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)
            serializer = ThresholdAmountSerializer(threshold_qs, many=True)
            logger.info(f"Successfully loaded bankruptcy config")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading bankruptcy config: {e}")
            return []

    def _load_ftb_config(self, type_id: int) -> list:
        """Load FTB related configuration data."""
        try:
            queryset = ExemptConfig.objects.select_related('state', 'pay_period', 'garnishment_type').filter(garnishment_type=type_id)
            config_ids = queryset.values_list("id", flat=True)
            threshold_qs = ThresholdAmount.objects.select_related("config").filter(config_id__in=config_ids)
            serializer = ThresholdAmountSerializer(threshold_qs, many=True)
            logger.info(f"Successfully loaded FTB config for type {type_id}")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading FTB config for type {type_id}: {e}")
            return []

    def preload_garnishment_fees(self) -> list:
        """
        Preloads garnishment fee configurations from the DB once.
        """
        try:
            fees = (
                GarnishmentFees.objects
                .select_related("state", "garnishment_type", "pay_period", "rule")
                .all()
                .order_by("-created_at")
            )
            serializer = GarnishmentFeesSerializer(fees, many=True)
            logger.info("Successfully loaded garnishment fee config")
            return serializer.data
        except Exception as e:
            logger.error(f"Error loading garnishment fees: {e}", exc_info=True)
            return []
