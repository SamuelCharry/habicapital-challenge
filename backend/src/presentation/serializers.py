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
    operation_id = serializers.UUIDField(source="entry.operation_id")
    operation_type = serializers.CharField(source="entry.operation_type")
    amount_minor = StrictIntegerField(source="entry.money.amount_minor")
    currency = serializers.CharField(source="entry.money.currency")
    created_at = serializers.DateTimeField(source="entry.created_at")
    counterparty_handle = serializers.CharField()
