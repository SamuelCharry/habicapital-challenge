from src.domain.events import TransferCompleted
from src.domain.repositories import SharedExpenseRepository
from src.domain.shared_expenses import SharedExpense


class SharedExpenseUpdater:
    def __init__(self, expenses: SharedExpenseRepository):
        self.expenses = expenses

    def __call__(self, event: TransferCompleted) -> SharedExpense | None:
        # Refresh from committed transfers. There is no mutable paid amount to
        # update, and a missed or repeated event cannot corrupt payment state.
        if event.shared_expense_id is not None:
            return self.expenses.get(event.shared_expense_id)
        return None
