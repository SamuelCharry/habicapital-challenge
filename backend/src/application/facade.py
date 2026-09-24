from uuid import UUID

from src.domain.money import Money
from .commands import CreateAccountCommand, DepositCommand, TransferCommand, CreateSharedExpenseCommand
from .services import AccountBalance, AccountService, DepositResult, DepositService, HistoryItem, TransferResult, TransferService, SharedExpenseService
from src.domain.shared_expenses import SharedExpense


class WalletFacade:
    def __init__(self, accounts: AccountService, deposits: DepositService, transfers: TransferService, expenses: SharedExpenseService):
        self.accounts = accounts
        self.deposits = deposits
        self.transfers = transfers
        self.expenses = expenses

    def create_account(self, handle: str, display_name: str) -> AccountBalance:
        return self.accounts.create(CreateAccountCommand(handle, display_name))

    def list_accounts(self) -> list[AccountBalance]:
        return self.accounts.list_accounts()

    def get_account(self, account_id: UUID) -> AccountBalance:
        return self.accounts.get(account_id)

    def balance(self, account_id: UUID) -> Money:
        return self.accounts.balance(account_id)

    def history(self, account_id: UUID) -> list[HistoryItem]:
        return self.accounts.history(account_id)

    def deposit(self, account_id: UUID, amount_minor: int, currency: str) -> DepositResult:
        return self.deposits.deposit(DepositCommand(account_id, Money(amount_minor, currency)))

    def transfer(
        self, source_account_id: UUID, destination_account_id: UUID,
        amount_minor: int, currency: str, idempotency_key: str,
        shared_expense_id: UUID | None = None,
    ) -> TransferResult:
        return self.transfers.transfer(TransferCommand(
            source_account_id, destination_account_id, Money(amount_minor, currency), idempotency_key,
            shared_expense_id,
        ))

    def create_shared_expense(
        self, title: str, total_minor: int, currency: str, payer_account_id: UUID,
        participant_account_ids: list[UUID], split: str,
    ) -> SharedExpense:
        return self.expenses.create(CreateSharedExpenseCommand(
            title, Money(total_minor, currency), payer_account_id, tuple(participant_account_ids), split,
        ))

    def get_shared_expense(self, expense_id: UUID) -> SharedExpense:
        return self.expenses.get(expense_id)

    def list_shared_expenses(self, account_id: UUID | None = None) -> list[SharedExpense]:
        return self.expenses.list_expenses(account_id)
