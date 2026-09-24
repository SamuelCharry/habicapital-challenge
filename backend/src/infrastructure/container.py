from src.application.facade import WalletFacade
from src.application.services import AccountService, DepositService
from .persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository


def build_wallet() -> WalletFacade:
    accounts = DjangoAccountRepository()
    ledger = DjangoLedgerRepository()
    return WalletFacade(AccountService(accounts, ledger), DepositService(accounts, ledger))
