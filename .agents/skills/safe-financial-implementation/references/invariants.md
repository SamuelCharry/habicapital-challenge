# Financial invariants

Each invariant states the rule, how it breaks, and how it is tested.
A change that touches money must keep every one of these true.

## INV-1 Conservation

**Rule.** Conservation is global and has no exceptions. Every operation
that touches money — including a simulated external deposit — writes
ledger entries that sum to zero per currency. Money never enters or
leaves the ledger; it only moves between accounts.

Money that originates outside the system enters through a dedicated
system account, `EXTERNAL_FUNDING`, which is the only account permitted
to hold a negative balance. Loading 50,000 into a user account writes
`-50,000` against `EXTERNAL_FUNDING` and `+50,000` against the user.
There is no such thing as a one-sided entry.

**Breaks when.** One side is written and the other is not; a deposit is
modelled as a single credit with no counterparty; an entry carries a
rounding adjustment that has no counterpart; a fee is debited without a
matching credit to a fee account.

**Test.** Two levels, both required.

- Per operation: `sum(entries.amount) == 0` grouped by operation id and
  currency.
- Globally: `sum(entries.amount) == 0` across the entire ledger, per
  currency, after any sequence of operations. This is the single query
  that answers "how do we know the system has not lost a peso".

**Note.** `EXTERNAL_FUNDING` is exempt from INV-3 (sufficient funds) and
from nothing else. Its negative balance is the measure of how much money
has been injected into the system, and is expected.

## INV-2 Positive amounts

**Rule.** Amount must be strictly greater than zero. Sign is expressed
by the entry's direction, never by a negative input amount.

**Breaks when.** Validation lives only in the serializer and a second
entry point bypasses it.

**Test.** Zero, negative, and non-numeric amounts are rejected at the
domain level, not only at the HTTP level.

## INV-3 Sufficient funds

**Rule.** An account cannot spend more than its available balance. The
sole exception is the `EXTERNAL_FUNDING` system account (see INV-1),
which represents money entering from outside and is expected to run
negative. No user account is ever exempt.

**Breaks when.** The balance is read outside the lock, so two concurrent
transfers both observe the pre-debit balance.

**Test.** Concurrency test: two transfers of the full balance issued in
parallel — exactly one succeeds, the other fails with insufficient funds.

## INV-4 Atomicity

**Rule.** A financial operation completes entirely or leaves no trace.

**Breaks when.** A side effect (notification, cached balance update,
external call) runs mid-transaction and the transaction later rolls back;
or a repository commits independently.

**Test.** Inject a failure after the first entry is written; assert the
ledger contains zero entries for that operation.

## INV-5 Idempotency

**Rule.** Replaying a command with the same idempotency key produces the
same result and exactly one financial effect.

**Breaks when.** The key is checked with a read before the write instead
of being enforced by a unique constraint — two concurrent retries both
pass the check.

**Test.** Same key submitted twice sequentially and twice concurrently;
one ledger operation exists and both calls return the same response.

## INV-6 Precision

**Rule.** Money is never a binary float. Arithmetic uses integer minor
units or `Decimal` with a declared scale, and every rounding point is
explicit.

**Breaks when.** A split divides an amount among N participants and the
remainder is dropped; JSON parsing turns an amount into a float.

**Test.** Splitting an indivisible amount distributes the remainder
deterministically and the parts sum exactly to the whole.

## INV-7 Immutable history

**Rule.** Ledger entries are append-only. A mistake is corrected with a
compensating entry that references the original.

**Breaks when.** Code updates or deletes an entry to "fix" a balance.

**Test.** Repository exposes no update or delete for entries; attempting
one raises.

## INV-8 Distinct counterparties

**Rule.** A transfer's source and destination must differ.

**Breaks when.** The check is missing and the self-transfer also
deadlocks against its own row lock.

**Test.** Self-transfer is rejected before any lock is taken.

## INV-9 Account state

**Rule.** Closed, frozen, or nonexistent accounts cannot participate in
new operations. State is checked inside the lock.

**Breaks when.** The account is closed between the state check and the
write.

**Test.** Close an account inside a concurrent transaction and assert
the in-flight transfer fails.

## INV-10 Reconcilable balance

**Rule.** Any cached or denormalized balance equals the sum of that
account's ledger entries.

**Status in this project: satisfied by construction.** There is no
cached balance column. `balance(account)` is always computed as
`SUM(ledger_entries.amount)` for that account, so the ledger and the
balance cannot diverge — there is nothing to diverge from. The account
row still exists and is the target of `SELECT ... FOR UPDATE`, but it
stores no monetary amount.

**Breaks when.** Someone introduces a cached balance for performance and
a write path updates the ledger but forgets the cache, or vice versa.

**Test.** If a cache is ever added, a reconciliation check after a
randomized sequence of operations becomes mandatory before it ships.

## Failure-mode checklist

Run through this before declaring a money-touching change complete:

- duplicate request / repeated idempotency key
- insufficient balance, exactly-equal balance, zero balance
- two concurrent transfers on the same account
- reversed lock order between two accounts (deadlock)
- rollback after partial write
- same sender and receiver
- nonexistent, closed, or frozen account
- amount of zero, negative, enormous, or with excess decimal places
- currency mismatch between accounts
- rounding remainder in a split
- database failure or timeout mid-operation
- side effect executed before commit
