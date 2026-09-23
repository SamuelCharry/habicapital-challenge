# habicapital-challenge

Financial system — backend and frontend.

## Structure

```
backend/     application, domain, infrastructure, presentation
frontend/    client
.agents/     agent skills and reference material
AGENTS.md    agent workflow contract
PLAN.md      per-task architecture plan (generated per task)
```

## Working with agents

Architecture and implementation are split across two agents. Claude
writes `PLAN.md`; Codex implements it following
`.agents/skills/safe-financial-implementation/SKILL.md`.

Read `AGENTS.md` for the full contract.

## Design rules that outlive any single task

- Layered architecture; dependencies point inward toward the domain.
- Money as integer minor units or `Decimal` — never `float`.
- Ledger is append-only; balances are derived, corrections are
  compensating entries.
- The application layer owns the transaction boundary.
- Every money-touching change defends the invariants in
  `.agents/skills/safe-financial-implementation/references/invariants.md`.

## Setup

Backend and frontend setup instructions land here once the stack is
committed.
