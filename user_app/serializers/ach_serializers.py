from rest_framework import serializers
from user_app.models import AchGarnishmentConfig


class AchGarnishmentConfigSerializer(serializers.ModelSerializer):
    # Input from user (labels)
    transaction_type = serializers.CharField(write_only=True, required=False, allow_null=True)
    service_class_type = serializers.CharField(write_only=True, required=False)
    # Allow omitting raw code when using service_class_type
    service_class_code = serializers.CharField(required=False, allow_blank=True)

    # Output (readable labels)
    transaction_type_display = serializers.SerializerMethodField(read_only=True)
    service_class_type_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AchGarnishmentConfig
        fields = "__all__"
        extra_kwargs = {
            "service_class_code": {"required": False},
        }
        # OR explicitly:
        # fields = [
        #     "id", "pay_date", "payment_type", "garnishment_type",
        #     "medical_support_indicator", "service_class_code",
        #     "service_class_type", "service_class_type_display",
        #     "account_type", "transaction_code", "transaction_type",
        #     "transaction_type_display", "company_id",
        #     "originating_routing_number", "originating_bank_name",
        #     "created_at", "updated_at"
        # ]

    # Mapping label → code
    SERVICE_CLASS_MAP = {
        "Credit & Debit": "200",
        "Credits Only": "220",
        "Debits Only": "225",
    }

    TRANSACTION_TYPE_MAP = {
        "Credit": "22",
        "Prenote Credit": "23",
        "Debit": "27",
        "Prenote Debit": "28",
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

        # ----- Transaction Code (only if checking) -----
        transaction_type = attrs.pop("transaction_type", None)

        if account_type == "checking":
            if not transaction_type and not attrs.get("transaction_code") and not (
                self.instance and self.instance.transaction_code
            ):
                raise serializers.ValidationError({
                    "transaction_type": "transaction_type is required when account_type is 'checking'."
                })

            if transaction_type:
                tx_code = self.TRANSACTION_TYPE_MAP.get(transaction_type)
                if not tx_code:
                    raise serializers.ValidationError({
                        "transaction_type": "Invalid transaction_type value."
                    })
                attrs["transaction_code"] = tx_code

        # Optional rule: if savings, don't allow transaction_code
        if account_type == "savings" and (transaction_type or attrs.get("transaction_code")):
            raise serializers.ValidationError({
                "transaction_code": "Transaction code should be empty when account_type is 'savings'."
            })

        return attrs

    # ---------- Display fields for response ----------

    def get_transaction_type_display(self, obj):
        if not obj.transaction_code:
            return None

        reverse_map = {v: k for k, v in self.TRANSACTION_TYPE_MAP.items()}
        return reverse_map.get(obj.transaction_code)

    def get_service_class_type_display(self, obj):
        reverse_map = {v: k for k, v in self.SERVICE_CLASS_MAP.items()}
        return reverse_map.get(obj.service_class_code)
