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
    shared_expense_id: UUID | None = None

    def __post_init__(self):
        if not isinstance(self.source_account_id, UUID) or not isinstance(self.destination_account_id, UUID):
            raise InvalidTransfer("Valid source and destination IDs are required.")
        if not isinstance(self.amount, Money) or not self.amount.is_positive or self.amount.amount_minor > 2**63 - 1:
            raise InvalidTransfer("A positive amount within the supported entry size is required.")
        if not isinstance(self.idempotency_key, str) or not 8 <= len(self.idempotency_key) <= 128:
            raise InvalidTransfer("An idempotency key of 8-128 characters is required.")
        if self.shared_expense_id is not None and not isinstance(self.shared_expense_id, UUID):
            raise InvalidTransfer('A valid shared expense ID is required.')


@dataclass(frozen=True)
class CreateSharedExpenseCommand:
    title: str
    total: Money
    payer_account_id: UUID
    participant_account_ids: tuple[UUID, ...]
    split: str = 'equal'

    def __post_init__(self):
        from src.domain.errors import InvalidSharedExpense

        if self.split != 'equal':
            raise InvalidSharedExpense('Only equal splitting is supported.')
        if (not isinstance(self.payer_account_id, UUID)
                or not self.participant_account_ids
                or any(not isinstance(i, UUID) for i in self.participant_account_ids)
                or len(set(self.participant_account_ids)) != len(self.participant_account_ids)
                or self.payer_account_id not in self.participant_account_ids):
            raise InvalidSharedExpense('Distinct participant IDs including the payer are required.')
