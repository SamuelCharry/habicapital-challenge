from datetime import datetime
from uuid import UUID, uuid5

from .entities import Account, EXTERNAL_FUNDING_ID, LedgerEntry
from .errors import InvalidDeposit
from .money import Money


class LedgerEntryFactory:
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
