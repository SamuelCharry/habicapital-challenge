from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from .entities import Account, EXTERNAL_FUNDING_ID
from .errors import InvalidSharedExpense
from .money import Money
from .split import SplitStrategy


@dataclass(frozen=True)
class Share:
    money: Money

    def __post_init__(self):
        if not isinstance(self.money, Money) or not self.money.is_positive:
            raise InvalidSharedExpense('Every share must be positive.')

    @property
    def amount_minor(self) -> int:
        return self.money.amount_minor


@dataclass(frozen=True)
class Participant:
    account: Account
    share: Share
    paid_minor: int = 0

    def __post_init__(self):
        if type(self.paid_minor) is not int or self.paid_minor < 0:
            raise InvalidSharedExpense('Paid amount must be a nonnegative integer.')

    @property
    def outstanding_minor(self) -> int:
        return max(0, self.share.amount_minor - self.paid_minor)

    @property
    def excess_minor(self) -> int:
        return max(0, self.paid_minor - self.share.amount_minor)

    @property
    def settled(self) -> bool:
        return self.outstanding_minor == 0


@dataclass(frozen=True)
class SharedExpense:
    id: UUID
    title: str
    total: Money
    payer: UUID
    participants: tuple[Participant, ...]

    def __post_init__(self):
        ids = [p.account.id for p in self.participants]
        if not isinstance(self.id, UUID) or not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 200:
            raise InvalidSharedExpense('A UUID and title of 1-200 characters are required.')
        if not isinstance(self.total, Money) or not 0 < self.total.amount_minor <= 2**63 - 1:
            raise InvalidSharedExpense('A positive total within the supported size is required.')
        if not ids or len(set(ids)) != len(ids) or self.payer not in ids or EXTERNAL_FUNDING_ID in ids:
            raise InvalidSharedExpense('Distinct user participants including the payer are required.')
        if (sum(p.share.amount_minor for p in self.participants) != self.total.amount_minor
                or any(p.share.money.currency != self.total.currency for p in self.participants)):
            raise InvalidSharedExpense('Shares must sum exactly to the total in the same currency.')

    @classmethod
    def create(
        cls, expense_id: UUID, title: str, total: Money, payer: UUID,
        accounts: Sequence[Account], strategy: SplitStrategy,
    ) -> 'SharedExpense':
        ids = [a.id for a in accounts]
        if len(ids) < 2 or len(set(ids)) != len(ids) or payer not in ids or EXTERNAL_FUNDING_ID in ids:
            raise InvalidSharedExpense('A shared expense needs at least two distinct participants, including the payer.')
        if not isinstance(total, Money) or not len(ids) <= total.amount_minor <= 2**63 - 1:
            raise InvalidSharedExpense('Total must allow a positive share for every participant.')
        shares = strategy.split(total, ids)
        if set(shares) != set(ids):
            raise InvalidSharedExpense('The strategy must return a share for each participant.')
        return cls(expense_id, title, total, payer, tuple(
            Participant(a, Share(shares[a.id]), shares[a.id].amount_minor if a.id == payer else 0)
            for a in accounts
        ))

    def validate_transfer(self, source: UUID, destination: UUID) -> None:
        if destination != self.payer or source == self.payer or source not in {p.account.id for p in self.participants}:
            raise InvalidSharedExpense('Expense transfers must be from a participant to the payer.')

    def with_payments(self, paid: Mapping[UUID, int]) -> 'SharedExpense':
        return replace(self, participants=tuple(
            replace(p, paid_minor=p.share.amount_minor if p.account.id == self.payer else paid.get(p.account.id, 0))
            for p in self.participants
        ))

    def paid_by(self, participant_id: UUID) -> Money:
        for participant in self.participants:
            if participant.account.id == participant_id:
                return Money(participant.paid_minor, self.total.currency)
        raise InvalidSharedExpense('Account is not a participant.')

    @property
    def outstanding_total_minor(self) -> int:
        return sum(p.outstanding_minor for p in self.participants)

    @property
    def settled(self) -> bool:
        return self.outstanding_total_minor == 0
