from uuid import UUID

import pytest

from src.domain.errors import InvalidSharedExpense
from src.domain.money import Money
from src.domain.split import EqualSplitStrategy


def ids(count):
    return [UUID(int=i + 10) for i in range(count)]


def test_equal_split_divides_evenly():
    assert list(EqualSplitStrategy().split(Money(180000), ids(3)).values()) == [Money(60000)] * 3


def test_equal_split_distributes_remainder_exactly():
    people = ids(3)
    shares = EqualSplitStrategy().split(Money(100000), list(reversed(people)))
    assert shares == dict(zip(people, [Money(33334), Money(33333), Money(33333)]))


def test_equal_split_sum_always_equals_total():
    strategy = EqualSplitStrategy()
    for count in range(2, 10):
        for total in range(count, 10001):
            amounts = [share.amount_minor for share in strategy.split(Money(total), ids(count)).values()]
            assert sum(amounts) == total
            assert min(amounts) > 0
            assert max(amounts) - min(amounts) <= 1


@pytest.mark.parametrize('total,count', [(1, 0), (0, 3), (-1, 3), (1, 3), (2, 3)])
def test_equal_split_rejects_zero_participants_non_positive_total_and_total_below_participant_count(total, count):
    with pytest.raises(InvalidSharedExpense):
        EqualSplitStrategy().split(Money(total), ids(count))


def test_equal_split_rejects_duplicate_participants():
    with pytest.raises(InvalidSharedExpense):
        EqualSplitStrategy().split(Money(100), ids(1) * 2)


@pytest.mark.parametrize('total', [2**53 + 1, 2**63 - 1])
def test_large_totals_keep_integer_precision(total):
    for count in range(1, 10):
        shares = EqualSplitStrategy().split(Money(total), ids(count))
        assert sum(s.amount_minor for s in shares.values()) == total
        assert all(type(s.amount_minor) is int and s.is_positive for s in shares.values())
