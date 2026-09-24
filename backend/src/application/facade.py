from uuid import UUID

from src.domain.money import Money
from .commands import CreateAccountCommand, DepositCommand
from .services import AccountBalance, AccountService, DepositResult, DepositService, HistoryItem


class WalletFacade:
    def __init__(self, accounts: AccountService, deposits: DepositService):
        self.accounts = accounts
        self.deposits = deposits

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
