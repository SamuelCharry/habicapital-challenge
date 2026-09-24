from dataclasses import dataclass
from uuid import UUID

from src.domain.entities import Account
from src.domain.errors import InvalidDeposit
from src.domain.money import Money


@dataclass(frozen=True)
class CreateAccountCommand:
    handle: str
    display_name: str

    def __post_init__(self):
        Account(UUID(int=0), self.handle, self.display_name)


@dataclass(frozen=True)
class DepositCommand:
    account_id: UUID
    amount: Money

    def __post_init__(self):
        if not isinstance(self.account_id, UUID) or not isinstance(self.amount, Money) or not self.amount.is_positive:
            raise InvalidDeposit("A valid account ID and positive amount are required.")
