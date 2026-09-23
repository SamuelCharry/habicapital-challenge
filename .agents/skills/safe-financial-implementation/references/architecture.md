# Architecture reference

Layered architecture. Dependencies point inward only.

```
presentation  ->  application  ->  domain
                      |              ^
                      v              |
                 infrastructure -----+
                 (implements domain/application ports)
```

## Layer contracts

### presentation

- HTTP views, serializers, URL routing, auth wiring.
- Validates request *shape* (types, required fields, format).
- Translates domain exceptions into HTTP status codes.
- Never computes balances, never opens a DB transaction, never touches
  the ORM directly.

### application

- Use cases / services. One public method per business operation.
- Owns the transaction boundary (`atomic`), not the domain, not the view.
- Builds Command objects from validated input.
- Depends on repository *interfaces*, never on concrete ORM classes.
- Publishes domain events after the transaction commits.

### domain

- Entities, value objects, domain services, strategies, factories,
  domain events, domain exceptions.
- Pure Python. No Django import, no ORM, no HTTP, no settings, no clock
  access except through an injected port.
- Enforces invariants that must hold regardless of storage.

### infrastructure

- ORM models, repository implementations, migrations, external clients.
- Maps between ORM rows and domain objects.
- The only place `select_for_update`, raw SQL, or vendor clients appear.

## Forbidden dependency edges

- domain -> django / infrastructure / presentation
- application -> ORM models or querysets
- presentation -> repositories or ORM
- infrastructure -> presentation

A violation of any of these is a defect even if tests pass.

## Transaction boundary

Exactly one place opens the transaction: the application use case.

- Repositories participate in the ambient transaction; they never open
  or commit their own.
- Domain objects are ignorant of transactions.
- Side effects that are not financially critical (email, audit push,
  webhooks) run *after* commit, never inside the transaction.

## Locking order

Concurrent transfers deadlock when two operations lock the same pair of
accounts in opposite order. Always acquire row locks in a deterministic
order — sort the account identifiers and lock ascending — regardless of
which account is the sender.

## Money representation

- Store as integer minor units, or `Decimal` with an explicit scale.
  Never `float`.
- Currency travels with the amount. A `Money` value object carries both;
  operations across differing currencies raise rather than coerce.
- Rounding is explicit and stated at the call site; never rely on a
  library default.

## Ledger model

Financial state is derived from an append-only ledger, not from mutating
a balance column in place.

- A transfer writes at least two entries (debit + credit) that sum to zero.
- Entries are immutable once written. Corrections are new compensating
  entries, never updates or deletes.
- A cached balance column, if present, is an optimization that must be
  reconcilable against the ledger.

## Testing seams

- Repositories are injected, so use cases are testable with in-memory
  fakes and no database.
- Time, UUID generation, and external calls are injected ports.
- Domain rules are unit-tested without Django.
- At least one integration test per financial operation exercises the
  real transaction and real locking.
