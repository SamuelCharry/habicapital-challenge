from src.application.facade import WalletFacade
from src.application.services import AccountService, DepositService, TransferService
from .persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository, DjangoTransferOperationRepository


def build_wallet() -> WalletFacade:
    accounts = DjangoAccountRepository()
    ledger = DjangoLedgerRepository()
    return WalletFacade(
        AccountService(accounts, ledger), DepositService(accounts, ledger),
        TransferService(accounts, ledger, DjangoTransferOperationRepository()),
    )
