# PLAN — GOAL 2: Safe transfers

Status: awaiting implementation by Codex.

GOAL 0 and GOAL 1 are closed and committed. Build on them.

This is the most important goal in the project. The challenge's single
non-negotiable rule is that the system cannot lose a peso, and transfers are
where money can actually be lost. Correctness here outranks everything else,
including finishing quickly.

## Goal

Move money between two user accounts, safely, under concurrency, with
idempotent retries. This completes the fifth and last mandatory feature of
the challenge core.

A transfer either happens exactly once and completely, or it does not happen
at all and leaves no trace. There is no third outcome.

## Affected components

**Domain**

- `backend/src/domain/factories.py` — add `LedgerEntryFactory.for_transfer(...)`
- `backend/src/domain/errors.py` — add `InsufficientFunds`, `SameAccountTransfer`,
  `IdempotencyConflict`
- `backend/src/domain/repositories.py` — add locking and idempotency methods

**Application**

- `backend/src/application/commands.py` — add `TransferCommand`
- `backend/src/application/services.py` — add `TransferService`
- `backend/src/application/facade.py` — expose `transfer(...)`

**Infrastructure**

- `backend/src/infrastructure/persistence/models.py` — add `TransferOperationModel`
- `backend/src/infrastructure/persistence/repositories.py` — implement locking
  and idempotency
- `backend/src/infrastructure/persistence/migrations/0003_transfers.py`
- `backend/src/infrastructure/container.py` — wire `TransferService`

**Presentation**

- `backend/src/presentation/controllers/transfers.py`
- `backend/src/presentation/serializers.py` — add transfer serializers
- `backend/config/urls.py` — mount `POST /api/transfers/`

**Tests**

- `backend/tests/domain/test_transfer_factory.py`
- `backend/tests/application/test_transfer_service.py` (fakes, no DB)
- `backend/tests/integration/test_transfers_api.py`
- `backend/tests/integration/test_transfer_concurrency.py` (real threads)

## Layer assignment

| Unit | Layer | Why |
|---|---|---|
| `for_transfer`, transfer errors | domain | The balanced-pair rule and the money rules hold regardless of storage. |
| `TransferCommand`, `TransferService` | application | Owns the transaction boundary and the operation sequence. |
| `TransferOperationModel`, locking, idempotency lookup | infrastructure | Row locks and unique constraints are database mechanics. |
| `transfers.py` controller | presentation | Request shape in, HTTP out. It must not know what a lock is. |

`SELECT ... FOR UPDATE` appears only in the repository implementation.
`transaction.atomic` appears only in `TransferService`.

## Patterns

No new pattern is introduced. Transfers reuse Command, Repository, Factory,
Facade and dependency injection exactly as deposits do. If a transfer needs a
new pattern to work, something is wrong with the design — say so instead of
adding one.

`LedgerEntryFactory.for_transfer` mirrors `for_deposit`: it returns the
**pair**, so a one-sided transfer is unobtainable.

## Invariants at risk

Every invariant in `references/invariants.md` is live in this goal.

- **INV-1 (conservation).** Two entries summing to zero, one `operation_id`.
  The failure mode is writing one side and committing.
- **INV-3 (sufficient funds).** The dangerous failure is a time-of-check to
  time-of-use race: reading the balance outside the lock lets two concurrent
  transfers both observe funds that only cover one of them. **The balance
  must be read after the locks are held.**
- **INV-4 (atomicity).** One `atomic` block covering the idempotency record,
  both ledger entries, and nothing else. No side effects inside it.
- **INV-5 (idempotency).** The dangerous failure is checking for an existing
  key with a `SELECT` and then inserting. Two concurrent retries both pass
  that check. **Uniqueness must be enforced by a database constraint**, and
  the duplicate must be detected by catching the integrity error.
- **INV-6 (precision).** Integer minor units throughout, as in GOAL 1.
- **INV-7 (immutable history).** The GOAL 1 trigger already covers this.
- **INV-8 (distinct counterparties).** Self-transfer is rejected *before* any
  lock is taken — otherwise the operation deadlocks against its own row.
- **INV-9 (account state).** Both accounts must exist. `EXTERNAL_FUNDING`
  cannot be either side of a user transfer.

## Decisions

1. **Deterministic lock order.** Both account rows are locked with
   `SELECT ... FOR UPDATE` in ascending order of account UUID, **always**,
   regardless of which is the sender. This is the whole defence against
   deadlock: two simultaneous opposite transfers (A→B and B→A) otherwise grab
   the rows in opposite order and wait on each other forever.
2. **Idempotency is a table, not a check.** `TransferOperationModel` has
   `idempotency_key` with a `UNIQUE` constraint. The service inserts that row
   first, inside the transaction. A duplicate raises `IntegrityError`, which
   is the signal that this request already happened. There is no
   `SELECT ... if not exists ... INSERT`, because two concurrent retries both
   survive that pattern.
3. **A replayed key returns the original result, not an error.** Same key,
   same request → `200 OK` with the body of the original transfer. First
   time → `201 Created`. The caller cannot tell how many times it retried,
   which is the point.
4. **Same key, different request → `409 Conflict`.** `TransferOperationModel`
   stores a `request_fingerprint` (a hash over source, destination, amount and
   currency). If the key matches but the fingerprint does not, the client has
   reused a key for a different operation; that is a bug on their side and
   must be surfaced loudly, never silently treated as a replay.
5. **The balance check happens after locking.** Sequence inside `atomic`:
   reject self-transfer → insert idempotency row → lock both accounts in UUID
   order → read source balance → check sufficiency → append the entry pair.
6. **`EXTERNAL_FUNDING` is not a valid party.** Transfers are user-to-user.
   Funding only moves through deposits.
7. **The idempotency row stores the resulting `operation_id`** so a replay can
   reconstruct the original response without recomputing anything.
8. **No retry loop, no backoff, no queue.** If the database raises a
   serialization or deadlock error, it propagates as a 500. Adding retry
   machinery now would hide the very races these tests exist to detect.

## Interfaces

```python
@dataclass(frozen=True)
class TransferCommand:
    source_account_id: UUID
    destination_account_id: UUID
    amount: Money
    idempotency_key: str
```

Repository additions:

```python
class AccountRepository(ABC):
    def lock_for_update(self, account_ids: Sequence[UUID]) -> list[Account]:
        """Lock the given accounts in ascending UUID order. Raises
        AccountNotFound if any is missing."""

class TransferOperationRepository(ABC):
    def claim(self, key: str, fingerprint: str, operation_id: UUID) -> None:
        """Insert the idempotency record. Raises DuplicateIdempotencyKey if
        the key already exists."""
    def get(self, key: str) -> TransferOperation: ...
```

HTTP:

```
POST /api/transfers/
{
  "source_account_id": "...",
  "destination_account_id": "...",
  "amount_minor": 6000000,
  "currency": "COP",
  "idempotency_key": "any-client-string"
}

201 {"operation_id", "source_balance_minor", "destination_balance_minor",
     "currency", "replayed": false}
200 same body with "replayed": true        — same key, same request
409 {"detail": "..."}                      — same key, different request
400                                        — non-positive amount, same account,
                                             funding account, bad shape
404                                        — source or destination missing
422 {"detail": "Insufficient funds."}       — INV-3
```

`idempotency_key`: 8–128 characters, required. A transfer without one is
rejected with 400 — for money movement, retry safety is not optional.

## Required tests

Domain (no DB):

1. `test_transfer_factory_returns_balanced_pair` — two entries, sum zero, one
   shared `operation_id`. INV-1.
2. `test_transfer_factory_rejects_non_positive_amount` — INV-2.
3. `test_transfer_factory_rejects_same_account` — INV-8.

Application (fakes, no DB):

4. `test_transfer_service_locks_before_reading_balance` — use a fake
   repository that records call order; assert `lock_for_update` is called
   before the balance is read. This is the INV-3 race, made into a test that
   fails if someone reorders the code.
5. `test_transfer_service_rejects_insufficient_funds`.

Integration (real PostgreSQL):

6. `test_transfer_moves_money_and_both_balances_change`.
7. `test_transfer_rejects_insufficient_funds_and_writes_nothing` — assert the
   ledger is unchanged afterwards, not merely that the response was 422.
8. `test_transfer_rejects_same_account` — INV-8.
9. `test_transfer_rejects_zero_and_negative` — INV-2.
10. `test_transfer_rejects_unknown_source_and_destination`.
11. `test_transfer_rejects_external_funding_as_either_party`.
12. `test_replayed_idempotency_key_returns_original_result` — sequential;
    exactly one operation exists afterwards. INV-5.
13. `test_same_key_different_payload_returns_409` — INV-5.
14. `test_rollback_after_injected_failure_leaves_no_entries` — inject a
    failure after the first entry would be written; assert zero entries and
    **no orphaned idempotency row**, so the retry can still succeed. INV-4.

Concurrency (real threads, real connections, `django_db(transaction=True)`):

15. `test_concurrent_duplicate_idempotency_key_creates_one_transfer` — fire
    the same key from N threads simultaneously; exactly one ledger operation
    exists and every response describes the same transfer. INV-5.
16. `test_concurrent_transfers_cannot_overspend` — an account with exactly
    enough for one transfer, two threads each trying to spend all of it.
    Exactly one succeeds, one gets 422, and the final balance is never
    negative. INV-3.
17. `test_opposite_transfers_do_not_deadlock` — A→B and B→A fired
    simultaneously many times. Both complete, no deadlock error. This is the
    test that proves the lock ordering in Decision 1 does its job.
18. `test_global_conservation_after_concurrent_load` — after all concurrent
    tests' worth of mixed deposits and transfers, the whole ledger still sums
    to exactly zero. INV-1.

Concurrency tests must use real threads with separate database connections
and close them properly. A test that fakes concurrency proves nothing.

## Acceptance criteria

1. Every test above passes against PostgreSQL, repeatedly. Run the
   concurrency tests at least 5 times in a row to catch flakiness — a race
   that appears one run in five is a failing test, not a flaky one.
2. Total ledger sum is exactly zero after any mixture of operations.
3. No account except `EXTERNAL_FUNDING` can reach a negative balance.
4. `SELECT ... FOR UPDATE` appears only in the repository layer.
5. `transaction.atomic` for transfers appears only in `TransferService`.
6. A transfer cannot be issued without an idempotency key.
7. The existing 52 tests still pass.

## Out of scope

- shared expenses and any link between a transfer and a context (GOAL 3)
- domain events (GOAL 3)
- frontend (GOAL 4)
- transfer reversal, cancellation, scheduling, fees, limits
- authentication and authorisation
- retry/backoff machinery (Decision 8)
