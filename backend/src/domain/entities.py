from dataclasses import dataclass
from datetime import datetime
import re
from uuid import UUID

from .errors import InvalidAccount
from .money import Money

EXTERNAL_FUNDING_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class Account:
    id: UUID
    handle: str
    display_name: str
    allows_negative_balance: bool = False

    def __post_init__(self):
        system = self.id == EXTERNAL_FUNDING_ID
        if system:
            if self.handle != "EXTERNAL_FUNDING" or self.allows_negative_balance is not True:
                raise InvalidAccount("Invalid funding account.")
        elif not isinstance(self.handle, str) or not re.fullmatch(r"[a-z0-9_]{3,20}", self.handle) or self.allows_negative_balance is not False:
            raise InvalidAccount("Invalid user account.")
        if not isinstance(self.id, UUID) or not isinstance(self.display_name, str) or not self.display_name.strip() or len(self.display_name) > 200:
            raise InvalidAccount("A UUID and display name (1-200 characters) are required.")


@dataclass(frozen=True)
class LedgerEntry:
    id: UUID
    account_id: UUID
    counterparty_id: UUID
    operation_id: UUID
    operation_type: str
    money: Money
    created_at: datetime


@dataclass(frozen=True)
class TransferOperation:
    idempotency_key: str
    request_fingerprint: str
    operation_id: UUID
    source_balance: Money
    destination_balance: Money
