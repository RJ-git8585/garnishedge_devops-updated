from rest_framework import serializers
from user_app.models import AchGarnishmentConfig


class AchGarnishmentConfigSerializer(serializers.ModelSerializer):
    # Input from user (labels)
    transaction_type = serializers.CharField(write_only=True, required=False, allow_null=True)
    transaction_code_type = serializers.CharField(write_only=True, required=False, allow_null=True, 
                                                   help_text="Alternative to transaction_type. Accepts: Credit, Prenote Credit, Debit, Prenote Debit")
    service_class_type = serializers.CharField(write_only=True, required=False)
    # Allow omitting raw code when using service_class_type
    service_class_code = serializers.CharField(required=False, allow_blank=True)

    # Output (readable labels) - Note: transaction_code_type is also used as input above
    transaction_code_type_display = serializers.SerializerMethodField(read_only=True)
    service_class_code_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AchGarnishmentConfig
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "service_class_code": {"required": False},
            "transaction_code": {"required": False, "allow_null": True, "allow_blank": True},
        }

    # Mapping label → code
    SERVICE_CLASS_MAP = {
        "Credit & Debit": "200",
        "Credits Only": "220",
        "Debits Only": "225",
    }

    # Transaction type mappings for checking accounts
    TRANSACTION_TYPE_MAP_CHECKING = {
        "Credit": "22",
        "Prenote Credit": "23",
        "Debit": "27",
        "Prenote Debit": "28",
    }

    # Transaction type mappings for savings accounts
    TRANSACTION_TYPE_MAP_SAVINGS = {
        "Credit": "32",
        "Prenote Credit": "33",
        "Debit": "37",
        "Prenote Debit": "38",
    }

    def validate(self, attrs):
        account_type = attrs.get("account_type") or getattr(self.instance, "account_type", None)

        # ----- Service Class Code -----
        service_class_type = attrs.pop("service_class_type", None)
        existing_service_class_code = attrs.get("service_class_code") or getattr(
            self.instance, "service_class_code", None
        )

        if service_class_type:
            code = self.SERVICE_CLASS_MAP.get(service_class_type)
            if not code:
                raise serializers.ValidationError({
                    "service_class_type": "Invalid service_class_type value."
                })
            attrs["service_class_code"] = code
        elif not existing_service_class_code:
            # If neither a code nor a type is supplied, raise a clear error
            raise serializers.ValidationError({
                "service_class_code": "Either service_class_type or service_class_code is required."
            })

        # ----- Transaction Code (automatically set based on account_type and transaction_type) -----
        transaction_type = attrs.pop("transaction_type", None)
        transaction_code_type = attrs.pop("transaction_code_type", None)
        
        # If transaction_code_type is provided but transaction_type is not, use transaction_code_type as transaction_type
        if transaction_code_type and not transaction_type:
            transaction_type = transaction_code_type
        
        # Get the old account_type from instance to detect account_type changes
        old_account_type = None
        if self.instance:
            old_account_type = getattr(self.instance, "account_type", None)
        
        # Check if account_type is being changed
        account_type_changed = old_account_type and old_account_type != account_type
        
        # If transaction_type is provided, it takes precedence - remove any existing transaction_code from attrs
        # to avoid conflicts, and we'll set it based on transaction_type
        if transaction_type:
            # Remove transaction_code from attrs if present, as we'll set it based on transaction_type
            attrs.pop("transaction_code", None)
        
        # Get existing transaction_code only if transaction_type is not provided
        existing_transaction_code = None
        if not transaction_type:
            existing_transaction_code = attrs.get("transaction_code") or (
                self.instance and self.instance.transaction_code
            )

        if account_type == "checking":
            # If transaction_type is provided, automatically set transaction_code
            if transaction_type:
                tx_code = self.TRANSACTION_TYPE_MAP_CHECKING.get(transaction_type)
                if not tx_code:
                    raise serializers.ValidationError({
                        "transaction_type": f"Invalid transaction_type value. Valid values: {list(self.TRANSACTION_TYPE_MAP_CHECKING.keys())}"
                    })
                attrs["transaction_code"] = tx_code
            # If transaction_type is not provided
            elif not existing_transaction_code:
                # For checking accounts, transaction_type is required if no existing code
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when account_type is 'checking'."
                })
            # If account_type changed, require transaction_type to set correct code
            elif account_type_changed:
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when changing account_type to 'checking'."
                })
            # If transaction_code exists and account_type didn't change, validate it's a checking code
            elif existing_transaction_code not in ["22", "23", "27", "28"]:
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when account_type is 'checking'. The existing transaction_code is not valid for checking accounts."
                })

        elif account_type == "savings":
            # If transaction_type is provided, automatically set transaction_code
            if transaction_type:
                tx_code = self.TRANSACTION_TYPE_MAP_SAVINGS.get(transaction_type)
                if not tx_code:
                    raise serializers.ValidationError({
                        "transaction_type": f"Invalid transaction_type value. Valid values: {list(self.TRANSACTION_TYPE_MAP_SAVINGS.keys())}"
                    })
                attrs["transaction_code"] = tx_code
            # If transaction_type is not provided
            elif not existing_transaction_code:
                # For savings accounts, transaction_type is required if no existing code
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when account_type is 'savings'."
                })
            # If account_type changed, require transaction_type to set correct code
            elif account_type_changed:
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when changing account_type to 'savings'."
                })
            # If transaction_code exists and account_type didn't change, validate it's a savings code
            elif existing_transaction_code not in ["32", "33", "37", "38"]:
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when account_type is 'savings'. The existing transaction_code is not valid for savings accounts."
                })

        return attrs

    # ---------- Display fields for response ----------

    def get_transaction_code_type_display(self, obj):
        if not obj.transaction_code:
            return None

        # Determine which mapping to use based on transaction_code
        # Checking codes: 22, 23, 27, 28
        # Savings codes: 32, 33, 37, 38
        if obj.transaction_code in ["22", "23", "27", "28"]:
            reverse_map = {v: k for k, v in self.TRANSACTION_TYPE_MAP_CHECKING.items()}
        elif obj.transaction_code in ["32", "33", "37", "38"]:
            reverse_map = {v: k for k, v in self.TRANSACTION_TYPE_MAP_SAVINGS.items()}
        else:
            return None

        return reverse_map.get(obj.transaction_code)
    
    def to_representation(self, instance):
        """Override to add transaction_code_type to output for backward compatibility"""
        representation = super().to_representation(instance)
        # Add transaction_code_type as read-only output (same as transaction_code_type_display)
        representation['transaction_code_type'] = self.get_transaction_code_type_display(instance)
        return representation

    def get_service_class_code_type(self, obj):
        reverse_map = {v: k for k, v in self.SERVICE_CLASS_MAP.items()}
        return reverse_map.get(obj.service_class_code)
