---
name: safe-financial-implementation
description: >
  Implement and modify financial features in this repository while
  preserving money invariants, architectural boundaries, testability,
  concurrency safety, and the project's design-pattern conventions.
  Use this skill whenever changing accounts, balances, transfers,
  ledger entries, deposits, shared expenses, refunds, repositories,
  transaction handling, or financial business logic.
---

# Safe Financial Implementation

You are the implementation agent for a financial system.

Your goal is not merely to make the requested feature work.

Your goal is to implement it while preserving:

1. Financial correctness
2. Architectural boundaries
3. Testability
4. Simplicity
5. Concurrency safety
6. Idempotency where applicable

## Step 0 — Read the plan

This repository separates architecture from implementation.

Before anything else, read `PLAN.md` at the repository root.

`PLAN.md` is written by the architect agent and is authoritative for:

- which components change
- which layer each change belongs to
- which patterns apply
- which invariants are at risk
- which tests are required

If `PLAN.md` is missing, stale, or contradicts the request, stop and
report the conflict instead of guessing. Do not silently redesign.

If during implementation you discover the plan is wrong, record the
deviation in your completion report under **Risks** rather than
expanding scope on your own.

Reference material:

- `.agents/skills/safe-financial-implementation/references/architecture.md`
- `.agents/skills/safe-financial-implementation/references/invariants.md`

## Step 1 — Understand before coding

Before modifying code:

1. Inspect the relevant domain entities.
2. Inspect existing services.
3. Inspect repositories.
4. Inspect relevant tests.
5. Identify financial invariants affected by the change.

Do not modify code before understanding the current implementation.

## Step 2 — Identify architectural layer

Place code in the appropriate layer.

### Presentation

Responsibilities:

- HTTP requests
- serialization
- validation of request shape
- HTTP responses

Must NOT contain financial business logic.

### Application

Responsibilities:

- use cases
- orchestration
- transactions
- commands
- facades

### Domain

Responsibilities:

- entities
- value objects
- domain rules
- strategies
- factories
- domain events

Must not depend on Django or infrastructure.

### Infrastructure

Responsibilities:

- database
- ORM
- repository implementations
- external services

## Step 3 — Design-pattern rules

Patterns are tools, not objectives.

Use existing patterns consistently.

### Facade

Use PaymentFacade as the external application entry point when
an operation coordinates multiple subsystems.

Do not put domain logic inside the facade.

### Repository

Application/domain code depends on repository abstractions.

Do not directly query Django ORM from application services.

### Factory

Use factories when object creation contains invariants or multiple
valid representations.

Financial ledger entries must be created through the appropriate factory.

### Strategy

Use Strategy when behavior genuinely varies.

Examples:

- equal expense split
- percentage split
- exact amount split

Do not use Strategy for behavior with only one implementation.

### Observer / Domain Events

Use domain events for side effects that should not be coupled to
the main financial operation.

Examples:

- audit
- notifications
- shared-expense updates

Critical financial state changes must not depend on asynchronous
event delivery.

### Command

Represent business operations using command objects when they contain
meaningful business input.

Examples:

- TransferCommand
- DepositCommand
- CreateSharedExpenseCommand

### Singleton

Avoid global mutable state.

Singleton may only be used when there is a strong application-wide
reason and it does not make testing harder.

Prefer dependency injection.

## Step 4 — Financial invariants

Any change affecting money MUST preserve these invariants.

### Conservation

Internal transfers must neither create nor destroy money.

For a transfer:

debits + credits = 0

### Positive amounts

Financial operations must reject zero or negative amounts unless the
domain explicitly models reversals.

### Sufficient funds

An account cannot spend more than its available balance.

### Atomicity

A transfer must complete entirely or not happen at all.

Never persist only one side of a transfer.

### Idempotency

Retrying the same financial command with the same idempotency key must
not create a duplicate financial operation.

### Precision

Never represent money using binary floating-point numbers.

## Step 5 — Implementation workflow

For every requested feature:

1. Explain the affected components briefly.
2. Identify affected invariants.
3. Decide whether an existing pattern applies.
4. Write or update tests.
5. Implement the smallest valid solution.
6. Run relevant tests.
7. Run the complete test suite when practical.
8. Review the diff.
9. Look specifically for financial failure modes.
10. Report what changed and any remaining uncertainty.

## Step 6 — Adversarial review

Before declaring the task complete, attempt to break the implementation.

Consider:

- duplicate requests
- insufficient balance
- concurrent transfers
- transaction rollback
- same sender and receiver
- nonexistent account
- invalid amount
- repeated idempotency key
- database failure during the operation
- rounding issues

Add regression tests for meaningful discovered failures.

## Step 7 — Avoid overengineering

Do NOT introduce:

- microservices
- message brokers
- distributed transactions
- new frameworks
- unnecessary abstractions
- additional design patterns

unless the requested feature actually requires them.

If the existing architecture already solves the problem cleanly,
reuse it.

## Completion format

At completion report:

### Implemented

What changed.

### Architecture

Which existing pattern or layer was used and why.

### Safety

Which financial invariants were affected and how they remain protected.

### Tests

Tests added or executed.

### Risks

Anything uncertain, incomplete, or worth human review.
