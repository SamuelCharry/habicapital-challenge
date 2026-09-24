from dataclasses import dataclass
import re

from .errors import InvalidMoney


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str = "COP"

    def __post_init__(self):
        if type(self.amount_minor) is not int:
            raise InvalidMoney("amount_minor must be an integer.")
        if self.currency != "COP":
            raise InvalidMoney("Only COP is supported.")

    @classmethod
    def from_decimal_string(cls, value: str, currency: str = "COP") -> "Money":
        if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", value):
            raise InvalidMoney("Expected a decimal string with at most two decimal places.")
        whole, _, fraction = value.lstrip("-").partition(".")
        minor = int(whole) * 100 + int(fraction.ljust(2, "0"))
        return cls(-minor if value.startswith("-") else minor, currency)

    def add(self, other: "Money") -> "Money":
        if not isinstance(other, Money) or self.currency != other.currency:
            raise InvalidMoney("Cannot add different currencies.")
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def negated(self) -> "Money":
        return Money(-self.amount_minor, self.currency)

    @property
    def is_positive(self) -> bool:
        return self.amount_minor > 0
