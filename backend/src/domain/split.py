from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from .errors import InvalidSharedExpense
from .money import Money


class SplitStrategy(ABC):
    @abstractmethod
    def split(self, total: Money, participant_ids: Sequence[UUID]) -> dict[UUID, Money]:
        """Return positive shares summing exactly to total."""


class EqualSplitStrategy(SplitStrategy):
    def split(self, total: Money, participant_ids: Sequence[UUID]) -> dict[UUID, Money]:
        if (not participant_ids or any(not isinstance(i, UUID) for i in participant_ids)
                or len(set(participant_ids)) != len(participant_ids)):
            raise InvalidSharedExpense('Distinct participant IDs are required.')
        if not isinstance(total, Money) or total.amount_minor < len(participant_ids):
            raise InvalidSharedExpense('Total must allow a positive share for every participant.')
        quotient, remainder = divmod(total.amount_minor, len(participant_ids))
        return {
            participant_id: Money(quotient + (1 if index < remainder else 0), total.currency)
            for index, participant_id in enumerate(sorted(participant_ids))
        }
