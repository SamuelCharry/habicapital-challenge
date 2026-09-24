import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.domain.money import Money
from src.domain.errors import InvalidMoney


@pytest.mark.parametrize("value", [1.0, 0.1, True, "100", None])
def test_money_rejects_float_construction(value):
    with pytest.raises(InvalidMoney):
        Money(value)


def test_money_addition_across_currencies_raises():
    # Exercise the arithmetic guard independently of COP-only construction.
    foreign = object.__new__(Money)
    object.__setattr__(foreign, "amount_minor", 100)
    object.__setattr__(foreign, "currency", "USD")
    with pytest.raises(InvalidMoney):
        Money(100).add(foreign)
    with pytest.raises(InvalidMoney):
        Money(100, "USD")


@pytest.mark.parametrize("amount, positive", [(-1, False), (0, False), (1, True)])
def test_money_is_positive_boundary(amount, positive):
    assert Money(amount).is_positive is positive


def test_money_exact_arithmetic_and_decimal_construction():
    assert Money.from_decimal_string("123.45") == Money(12345)
    assert Money.from_decimal_string("-0.01") == Money(-1)
    assert Money(2**60).add(Money(1)).amount_minor == 2**60 + 1
    assert Money(12).negated() == Money(-12)
    with pytest.raises(FrozenInstanceError):
        Money(1).amount_minor = 2
    for value in ("0.001", "NaN", "Infinity", "1e2", 1.2):
        with pytest.raises(InvalidMoney):
            Money.from_decimal_string(value)


def test_domain_does_not_import_django():
    root = Path(__file__).resolve().parents[2] / "src" / "domain"
    files = list(root.rglob("*.py"))
    assert {p.name for p in files} >= {"money.py", "entities.py", "factories.py", "repositories.py"}
    forbidden = ("django", "rest_framework", "src.infrastructure", "infrastructure")
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module or ''}.{a.name}" for a in node.names]
                if node.level:
                    assert not any(a.name == "infrastructure" for a in node.names), path
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                assert name not in {"__import__", "import_module", "exec", "eval"}, path
            assert not any(name == prefix or name.startswith(prefix + ".") for name in names for prefix in forbidden), path


def test_json_parser_never_constructs_binary_numbers():
    from decimal import Decimal
    from io import BytesIO
    from src.presentation.serializers import ExactJSONParser

    parsed = ExactJSONParser().parse(BytesIO(b'{"amount_minor":9007199254740993.1}'))
    assert type(parsed["amount_minor"]) is Decimal
    assert parsed["amount_minor"] == Decimal("9007199254740993.1")
