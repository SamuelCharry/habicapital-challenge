from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from uuid import UUID

from .entities import Account, LedgerEntry
from .money import Money


class AccountRepository(ABC):
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
