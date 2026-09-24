from src.application.credit_service import CreditPathService
from src.application.facade import WalletFacade
from src.application.services import AccountService, DepositService, TransferService, SharedExpenseService
from src.application.event_handlers import SharedExpenseUpdater
from src.domain.events import EventDispatcher, TransferCompleted
from .credit.diffusion import load_model
from .persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository, DjangoTransferOperationRepository, DjangoSharedExpenseRepository


def build_wallet() -> WalletFacade:
    accounts = DjangoAccountRepository()
    ledger = DjangoLedgerRepository()
    expenses = DjangoSharedExpenseRepository()
    dispatcher = EventDispatcher()
    dispatcher.subscribe(TransferCompleted, SharedExpenseUpdater(expenses))
    return WalletFacade(
        AccountService(accounts, ledger, expenses=expenses), DepositService(accounts, ledger),
        TransferService(accounts, ledger, DjangoTransferOperationRepository(), expenses=expenses, dispatcher=dispatcher),
        SharedExpenseService(accounts, expenses),
        CreditPathService(accounts, ledger, expenses, load_model),
    )
