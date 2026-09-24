from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from uuid import UUID

from .entities import Account, LedgerEntry, TransferOperation
from .money import Money


class AccountRepository(ABC):
    @abstractmethod
    def lock_for_update(self, account_ids: Sequence[UUID]) -> list[Account]:
        """Lock accounts in ascending UUID order; raise AccountNotFound if missing."""

    @abstractmethod
    def add(self, account: Account) -> Account: ...

    @abstractmethod
    def get(self, account_id: UUID) -> Account: ...

    @abstractmethod
    def get_by_handle(self, handle: str) -> Account: ...

    @abstractmethod
    def handles_for(self, account_ids: Iterable[UUID]) -> dict[UUID, str]: ...

    @abstractmethod
    def list_user_accounts(self) -> list[Account]: ...

    @abstractmethod
    def balance_of(self, account_id: UUID) -> Money: ...


class LedgerRepository(ABC):
    @abstractmethod
    def append(self, entries: Sequence[LedgerEntry]) -> None:
        """Append the entire batch in the application's ambient transaction."""

    @abstractmethod
    def entries_for(self, account_id: UUID) -> list[LedgerEntry]: ...

    @abstractmethod
    def total_balance(self) -> Money: ...


class TransferOperationRepository(ABC):
    @abstractmethod
    def claim(self, key: str, fingerprint: str, operation_id: UUID) -> None:
        """Insert a claim, raising DuplicateIdempotencyKey for an existing key."""

    @abstractmethod
    def get(self, key: str) -> TransferOperation:
        """Read the committed original operation and its response balances."""

    @abstractmethod
    def complete(self, key: str, source_balance: Money, destination_balance: Money) -> None:
        """Store the response in the same application transaction as the claim."""
