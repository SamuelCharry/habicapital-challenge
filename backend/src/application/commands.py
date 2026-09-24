from dataclasses import dataclass
from uuid import UUID

from src.domain.entities import Account
from src.domain.errors import InvalidDeposit, InvalidTransfer
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


@dataclass(frozen=True)
class TransferCommand:
    source_account_id: UUID
    destination_account_id: UUID
    amount: Money
    idempotency_key: str

    def __post_init__(self):
        if not isinstance(self.source_account_id, UUID) or not isinstance(self.destination_account_id, UUID):
            raise InvalidTransfer("Valid source and destination IDs are required.")
        if not isinstance(self.amount, Money) or not self.amount.is_positive or self.amount.amount_minor > 2**63 - 1:
            raise InvalidTransfer("A positive amount within the supported entry size is required.")
        if not isinstance(self.idempotency_key, str) or not 8 <= len(self.idempotency_key) <= 128:
            raise InvalidTransfer("An idempotency key of 8-128 characters is required.")
