from datetime import datetime
from uuid import UUID, uuid5

from .entities import Account, EXTERNAL_FUNDING_ID, LedgerEntry
from .errors import InvalidDeposit, InvalidTransfer, SameAccountTransfer
from .money import Money


class LedgerEntryFactory:
    @staticmethod
    def for_transfer(
        source: Account, destination: Account, amount: Money, *,
        operation_id: UUID, created_at: datetime,
    ) -> tuple[LedgerEntry, LedgerEntry]:
        if source.id == destination.id:
            raise SameAccountTransfer("Source and destination must differ.")
        if EXTERNAL_FUNDING_ID in (source.id, destination.id):
            raise InvalidTransfer("Transfers require two user accounts.")
        if not isinstance(amount, Money) or not amount.is_positive:
            raise InvalidTransfer("Transfer amount must be positive.")
        if amount.amount_minor > 2**63 - 1:
            raise InvalidTransfer("Transfer amount exceeds the supported entry size.")
        return (
            LedgerEntry(
                uuid5(operation_id, "debit"), source.id, destination.id,
                operation_id, "transfer", amount.negated(), created_at,
            ),
            LedgerEntry(
                uuid5(operation_id, "credit"), destination.id, source.id,
                operation_id, "transfer", amount, created_at,
            ),
        )

    @staticmethod
    def for_deposit(
        account: Account, amount: Money, *, operation_id: UUID, created_at: datetime,
    ) -> tuple[LedgerEntry, LedgerEntry]:
        if not isinstance(amount, Money) or not amount.is_positive:
            raise InvalidDeposit("Deposit amount must be positive.")
        if amount.amount_minor > 2**63 - 1:
            raise InvalidDeposit("Deposit amount exceeds the supported entry size.")
        if account.id == EXTERNAL_FUNDING_ID:
            raise InvalidDeposit("Deposits require a user account.")
        # Derive entry IDs from the application-supplied operation identifier.
        debit = LedgerEntry(
            uuid5(operation_id, "debit"), EXTERNAL_FUNDING_ID, account.id,
            operation_id, "deposit", amount.negated(), created_at,
        )
        credit = LedgerEntry(
            uuid5(operation_id, "credit"), account.id, EXTERNAL_FUNDING_ID,
            operation_id, "deposit", amount, created_at,
        )
        return debit, credit
