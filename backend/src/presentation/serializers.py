from decimal import Decimal
import json

from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class ExactJSONParser(BaseParser):
    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        # Decode non-integral JSON tokens exactly; the integer field then rejects them.
        def reject_constant(value):
            raise ValueError("Non-finite JSON number")

        try:
            return json.loads(
                stream.read().decode("utf-8"),
                parse_float=Decimal, parse_constant=reject_constant,
            )
        except (ValueError, UnicodeError) as exc:
            raise ParseError("Invalid JSON.") from exc


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class CreateAccountSerializer(serializers.Serializer):
    handle = serializers.RegexField(r"^[a-z0-9_]{3,20}$", trim_whitespace=False)
    display_name = serializers.CharField(max_length=200)


class DepositSerializer(serializers.Serializer):
    amount_minor = StrictIntegerField(max_value=2**63 - 1)
    currency = serializers.ChoiceField(choices=["COP"])


class AccountSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="account.id")
    handle = serializers.CharField(source="account.handle")
    display_name = serializers.CharField(source="account.display_name")
    balance_minor = StrictIntegerField(source="balance.amount_minor")
    currency = serializers.CharField(source="balance.currency")


class BalanceSerializer(serializers.Serializer):
    balance_minor = StrictIntegerField(source="amount_minor")
    currency = serializers.CharField()


class DepositResultSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    balance_minor = StrictIntegerField(source="balance.amount_minor")
    currency = serializers.CharField(source="balance.currency")


class HistorySerializer(serializers.Serializer):
    shared_expense_id = serializers.UUIDField(allow_null=True)
    shared_expense_title = serializers.CharField(allow_null=True)
    operation_id = serializers.UUIDField(source="entry.operation_id")
    operation_type = serializers.CharField(source="entry.operation_type")
    amount_minor = StrictIntegerField(source="entry.money.amount_minor")
    currency = serializers.CharField(source="entry.money.currency")
    created_at = serializers.DateTimeField(source="entry.created_at")
    counterparty_handle = serializers.CharField()


class IdempotencyKeyField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class TransferSerializer(serializers.Serializer):
    shared_expense_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    source_account_id = serializers.UUIDField()
    destination_account_id = serializers.UUIDField()
    amount_minor = StrictIntegerField(max_value=2**63 - 1)
    currency = serializers.ChoiceField(choices=["COP"])
    idempotency_key = IdempotencyKeyField(min_length=8, max_length=128, trim_whitespace=False)


class TransferResultSerializer(serializers.Serializer):
    shared_expense_id = serializers.UUIDField(allow_null=True)
    operation_id = serializers.UUIDField()
    source_balance_minor = StrictIntegerField(source="source_balance.amount_minor")
    destination_balance_minor = StrictIntegerField(source="destination_balance.amount_minor")
    currency = serializers.CharField(source="source_balance.currency")
    replayed = serializers.BooleanField()


class CreateSharedExpenseSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    total_minor = StrictIntegerField(max_value=2**63 - 1)
    currency = serializers.ChoiceField(choices=['COP'])
    payer_account_id = serializers.UUIDField()
    participant_account_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    split = serializers.ChoiceField(choices=['equal'])


class ParticipantSerializer(serializers.Serializer):
    account_id = serializers.UUIDField(source='account.id')
    handle = serializers.CharField(source='account.handle')
    display_name = serializers.CharField(source='account.display_name')
    share_minor = StrictIntegerField(source='share.amount_minor')
    paid_minor = StrictIntegerField()
    outstanding_minor = StrictIntegerField()
    excess_minor = StrictIntegerField()
    settled = serializers.BooleanField()


class SharedExpenseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    total_minor = StrictIntegerField(source='total.amount_minor')
    currency = serializers.CharField(source='total.currency')
    payer = serializers.UUIDField()
    participants = ParticipantSerializer(many=True)
    outstanding_total_minor = StrictIntegerField()
    settled = serializers.BooleanField()


class CreditProfileSerializer(serializers.Serializer):
    monthly_savings_minor = StrictIntegerField(source='monthly_savings.amount_minor')
    months_consistent = StrictIntegerField()
    compliance_ratio = serializers.FloatField(allow_null=True)
    down_payment_minor = StrictIntegerField(source='down_payment.amount_minor')
    currency = serializers.CharField(source='monthly_savings.currency')


class WaypointSerializer(serializers.Serializer):
    capacity = serializers.FloatField()
    stability = serializers.FloatField()
    qualify_probability = serializers.FloatField()
    monthly_savings_minor = StrictIntegerField(source='monthly_savings.amount_minor')
    months_consistent = StrictIntegerField()


class StepSerializer(serializers.Serializer):
    order = StrictIntegerField()
    action = serializers.CharField()
    magnitude = serializers.CharField()


class CreditPathSerializer(serializers.Serializer):
    profile = CreditProfileSerializer()
    has_enough_evidence = serializers.BooleanField()
    headline = serializers.CharField()
    # Cada punto es [capacidad, estabilidad, probabilidad de calificar].
    population = serializers.ListField(child=serializers.ListField(child=serializers.FloatField()))
    generated = serializers.ListField(child=serializers.ListField(child=serializers.FloatField()))
    trajectory = WaypointSerializer(many=True)
    steps = StepSerializer(many=True)
