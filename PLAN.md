# PLAN — GOAL 1: Money, Account, Ledger, Deposit

Status: awaiting implementation by Codex.

Previous goal (GOAL 0 — foundation) is closed and committed. Build on it.

## Goal

Introduce money into the system. After this goal the API can create an
account, load simulated balance into it, report its balance, and list its
movements — four of the five mandatory features of the challenge. Transfers
between user accounts are **not** part of this goal.

The ledger model established here is what every later financial operation
sits on, so it is built correctly now rather than retrofitted.

## Affected components

**New — domain (pure Python, no Django import anywhere)**

- `backend/src/domain/__init__.py`
- `backend/src/domain/money.py` — `Money` value object
- `backend/src/domain/entities.py` — `Account`, `LedgerEntry`
- `backend/src/domain/factories.py` — `LedgerEntryFactory`
- `backend/src/domain/errors.py` — domain exceptions
- `backend/src/domain/repositories.py` — repository interfaces (ABCs)

**New — application**

- `backend/src/application/__init__.py`
- `backend/src/application/commands.py` — `CreateAccountCommand`, `DepositCommand`
- `backend/src/application/services.py` — `AccountService`, `DepositService`
- `backend/src/application/facade.py` — `WalletFacade`

**New — infrastructure**

- `backend/src/infrastructure/__init__.py`
- `backend/src/infrastructure/persistence/__init__.py` — Django app config
- `backend/src/infrastructure/persistence/models.py` — `AccountModel`, `LedgerEntryModel`
- `backend/src/infrastructure/persistence/repositories.py` — Django implementations
- `backend/src/infrastructure/persistence/migrations/` — generated
- `backend/src/infrastructure/container.py` — wires the facade

**New — presentation**

- `backend/src/presentation/controllers/accounts.py`
- `backend/src/presentation/serializers.py`

**New — tests**

- `backend/tests/domain/test_money.py`
- `backend/tests/domain/test_ledger_factory.py`
- `backend/tests/application/test_deposit_service.py` (fake repositories, no DB)
- `backend/tests/integration/test_accounts_api.py`
- `backend/tests/integration/test_conservation.py`

**Modified**

- `backend/config/settings.py` — register the persistence app
- `backend/config/urls.py` — mount account routes
- `frontend/package-lock.json` — commit it (see Decisions)
- `.github/workflows/ci.yml` — `npm ci` instead of `npm install`

## Layer assignment

| Unit | Layer | Why |
|---|---|---|
| `Money`, `Account`, `LedgerEntry` | domain | Rules that hold regardless of storage. |
| `LedgerEntryFactory` | domain | Creating entries carries invariants; creation must be controlled. |
| Repository ABCs | domain | The domain declares what it needs; infrastructure supplies it. |
| Commands, services, `WalletFacade` | application | Orchestration and the transaction boundary. |
| Django models, repository impls | infrastructure | The only place the ORM exists. |
| Controllers, serializers | presentation | Request shape in, HTTP out. No business rules. |

`domain/` must not import `django`, `rest_framework`, or anything from
`infrastructure/`. This is checked by a test.

## Patterns

Four patterns enter the codebase here. Each must earn its place.

**Repository** — application code depends on `AccountRepository` and
`LedgerRepository` abstract base classes. It never touches a queryset. This
is what makes `DepositService` testable without a database, which the
application test proves.

**Command** — `CreateAccountCommand` and `DepositCommand` are frozen
dataclasses carrying validated business input. They make the operation's
inputs explicit instead of passing loose arguments.

**Factory** — `LedgerEntryFactory.for_deposit(...)` returns the *pair* of
entries for a deposit. Its reason to exist: it is impossible to obtain a
single unbalanced entry through it. Callers cannot write a one-sided entry
because the factory never returns one.

**Facade** — `WalletFacade` is the single entry point the presentation layer
calls. It coordinates; it holds no business rules.

Dependency injection: services receive repositories through their
constructor. `container.py` does the wiring. Do **not** introduce a DI
framework, and do not make anything a singleton.

Not used in this goal: Strategy (nothing varies yet), Observer (no side
effects yet). Do not add them speculatively.

## Invariants at risk

- **INV-1 (conservation, global).** A deposit must write two entries:
  `-amount` against `EXTERNAL_FUNDING` and `+amount` against the target
  account. A one-sided deposit breaks conservation permanently and silently.
- **INV-2 (positive amounts).** Rejected in the domain, not only in the
  serializer, so a second entry point cannot bypass it.
- **INV-6 (precision).** `Money` holds `amount_minor: int`. No float may
  appear on any money path, including JSON parsing and serialization.
- **INV-7 (immutable history).** Ledger entries are append-only. The
  repository exposes no update or delete for entries.
- **INV-3 (sufficient funds).** Not exercised yet — deposits only add. But
  `EXTERNAL_FUNDING` must already be modelled as the one account allowed to
  go negative, because GOAL 2 depends on that distinction existing.
- **INV-10 (reconcilable balance).** Satisfied by construction: balance is
  `SUM(entries)`, there is no cached column.

## Decisions

1. **`Money`** is a frozen dataclass: `amount_minor: int`, `currency: str`
   (only `"COP"`). Arithmetic between different currencies raises. No
   `__float__`. Construction from a decimal string is explicit; there is no
   implicit float path.
2. **`EXTERNAL_FUNDING`** is a real row in the accounts table with a
   reserved identifier, created by a data migration so it always exists. It
   is the only account with `allows_negative_balance = True`. It is never
   returned by the public account-listing endpoint.
3. **Balance is always computed** as `SUM(ledger_entries.amount_minor)`. No
   balance column on `AccountModel`.
4. **Every ledger entry belongs to an operation.** `LedgerEntryModel` has an
   `operation_id` (UUID) grouping the entries written together, and an
   `operation_type` (`"deposit"` for now). This is what makes per-operation
   conservation checkable, and GOAL 2 reuses it for transfers.
5. **The deposit transaction boundary is in `DepositService`**, using
   `django.db.transaction.atomic`. Not in the view, not in the repository.
6. **Amounts cross the API as integer minor units** in a field named
   `amount_minor`, plus a `currency` field. No decimal strings, no floats, in
   either direction. The frontend formats for display; the API does not.
7. **Commit `frontend/package-lock.json`** and switch CI to `npm ci`. A
   financial application should build from a pinned dependency tree. This is
   carried-over debt from GOAL 0.

## Interfaces

Domain:

```python
@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str = "COP"
    def add(self, other: "Money") -> "Money": ...
    def negated(self) -> "Money": ...
    @property
    def is_positive(self) -> bool: ...
```

```python
class AccountRepository(ABC):
    def add(self, account: Account) -> Account: ...
    def get(self, account_id: UUID) -> Account: ...          # raises AccountNotFound
    def get_by_handle(self, handle: str) -> Account: ...
    def list_user_accounts(self) -> list[Account]: ...        # excludes EXTERNAL_FUNDING
    def balance_of(self, account_id: UUID) -> Money: ...

class LedgerRepository(ABC):
    def append(self, entries: Sequence[LedgerEntry]) -> None: ...   # all-or-nothing
    def entries_for(self, account_id: UUID) -> list[LedgerEntry]: ...
    def total_balance(self) -> Money: ...                            # must be zero
```

HTTP:

```
POST /api/accounts/            {"handle": "samuel", "display_name": "Samuel"}
  201 {"id", "handle", "display_name", "balance_minor", "currency"}
  400 on duplicate handle or invalid shape

GET  /api/accounts/            200 [ ...accounts... ]   (excludes EXTERNAL_FUNDING)
GET  /api/accounts/{id}/       200 {...}  | 404
GET  /api/accounts/{id}/balance/  200 {"balance_minor": 5000000, "currency": "COP"}
GET  /api/accounts/{id}/history/  200 [{"operation_id","operation_type","amount_minor",
                                        "currency","created_at","counterparty_handle"}]

POST /api/accounts/{id}/deposits/  {"amount_minor": 5000000, "currency": "COP"}
  201 {"operation_id", "balance_minor", "currency"}
  400 if amount_minor <= 0
  404 if account does not exist
```

`handle` is unique, lowercase, `^[a-z0-9_]{3,20}$`.

## Required tests

Domain (no database):

1. `test_money_rejects_float_construction` — INV-6.
2. `test_money_addition_across_currencies_raises` — INV-6.
3. `test_money_is_positive_boundary` — zero is not positive. INV-2.
4. `test_deposit_factory_returns_balanced_pair` — the two entries sum to
   zero and share one `operation_id`. INV-1.
5. `test_deposit_factory_rejects_non_positive_amount` — INV-2.

Application (fake in-memory repositories, no Django):

6. `test_deposit_service_appends_both_entries` — proves the service works
   without a database, which is the point of the Repository abstraction.
7. `test_deposit_service_rejects_unknown_account`.

Integration (real PostgreSQL):

8. `test_create_account_and_read_balance` — new account starts at zero.
9. `test_duplicate_handle_is_rejected` — DB unique constraint, not a
   pre-check.
10. `test_deposit_increases_balance_and_history`.
11. `test_deposit_rejects_zero_and_negative` — INV-2.
12. `test_global_ledger_sums_to_zero_after_deposits` — INV-1, the headline
    check: after a sequence of deposits, `SUM` over the whole ledger is
    exactly `0`.
13. `test_external_funding_is_negative_and_hidden` — funding balance equals
    minus the total deposited, and it never appears in `GET /api/accounts/`.
14. `test_ledger_entries_cannot_be_modified` — INV-7.

Architecture guard:

15. `test_domain_does_not_import_django` — walk `src/domain/**.py` and assert
    no module imports `django`, `rest_framework`, or `src.infrastructure`.

## Acceptance criteria

1. All tests above pass against PostgreSQL. No SQLite.
2. `grep -rn "float" backend/src` returns nothing on a money path.
3. `backend/src/domain/` contains no Django import, enforced by test 15.
4. Creating an account, depositing, reading balance and reading history all
   work through real HTTP calls.
5. After any sequence of deposits, total ledger sum is exactly zero.
6. `frontend/package-lock.json` is committed and CI uses `npm ci`.
7. Migrations exist and apply cleanly to an empty database.

## Out of scope

- transfers between user accounts (GOAL 2)
- idempotency keys and row locking (GOAL 2 — do not add them now)
- shared expenses, split strategies, domain events (GOAL 3)
- authentication, permissions, users beyond `handle` + `display_name`
- frontend changes beyond the committed lockfile (GOAL 4)
- withdrawals, reversals, fees, multi-currency

---

## FIX — review round 1

The goal is functionally correct and all 51 tests pass. Two changes before it
closes. Change nothing else.

### FIX-1 — Replace the raw SQL insert in the ledger repository

`DjangoLedgerRepository.append` builds an INSERT statement by concatenating
placeholder groups and passing a flattened parameter list. It is correct and
properly parameterized, but it is the single most important write path in the
system and it is the least readable code in the repository.

Replace it with `LedgerEntryModel.objects.bulk_create([...])`, which issues
the same single INSERT for the pair. Keep the `connection.in_atomic_block`
guard exactly as it is — that guard is the reason the repository cannot open
its own transaction, and it must survive this change.

Reason: this code has to be explained out loud and modified live during a
pair-programming interview. Hand-built SQL where the ORM does the same thing
in one line costs explanation budget and buys nothing.

### FIX-2 — Remove the N+1 in account history

`AccountService.history` calls `self.accounts.get(...)` once per ledger entry
to resolve the counterparty handle. Add a repository method that resolves the
handles for a set of account ids in one query, and use it.

Suggested signature on `AccountRepository`:

```python
def handles_for(self, account_ids: Iterable[UUID]) -> dict[UUID, str]: ...
```

Do not add caching. Do not change the HTTP response shape.

### Required for this fix

- The full suite still passes against PostgreSQL, unchanged in count and
  behaviour.
- Add one test asserting that reading the history of an account with several
  entries issues a bounded number of queries, using
  `django.test.utils.CaptureQueriesContext`. It must fail if the N+1 returns.
