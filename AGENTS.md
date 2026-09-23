# AGENTS.md

Instructions for AI agents working in this repository.

## Two-agent workflow

This repository separates **architecture** from **implementation**. The
two roles do not overlap.

```
Claude (architect)
   |
   |  writes the architecture plan
   v
PLAN.md
   |
   v
Codex (implementer)
   |
   |  follows .agents/skills/safe-financial-implementation/SKILL.md
   v
Implementation
   |
   v
Tests
```

### Claude — architect

Decides *what* and *where*. Produces `PLAN.md` at the repository root.

Does:

- read the existing code and tests before proposing anything
- choose the layer for each change
- choose which existing pattern applies, or state that none does
- enumerate the financial invariants the change puts at risk
- specify the tests that must exist before the change is considered done
- define interfaces and signatures when they cross a layer boundary

Does not:

- write implementation code
- write migrations
- run the test suite as a way of exploring the design

If the request is underspecified, the architect asks rather than assumes.
If the request is a one-line fix with no architectural content, the
architect says so instead of manufacturing a plan.

### Codex — implementer

Decides *how*, within the plan. Writes the code and the tests.

Does:

- read `PLAN.md` first, every time
- follow `.agents/skills/safe-financial-implementation/SKILL.md`
- write or update tests before implementing
- run the tests
- perform the adversarial review in Step 6 of the skill
- report using the completion format in the skill

Does not:

- redesign, introduce new patterns, or change layer assignments
- expand scope beyond `PLAN.md`
- delete or weaken an existing test to make a change pass
- mark work complete with failing or skipped tests

When implementation reveals the plan is wrong, Codex stops and reports
the conflict. It does not silently improvise a different architecture.

## PLAN.md contract

`PLAN.md` is regenerated per task and is authoritative while that task is
open. Required sections:

```markdown
# PLAN — <task name>

## Goal
One paragraph. What the user gets, stated in business terms.

## Affected components
Files and classes, grouped by layer.

## Layer assignment
For each new or changed unit: which layer, and why that one.

## Patterns
Which existing pattern is reused, or an explicit statement that plain
code is the right answer here.

## Invariants at risk
Reference the INV-n ids in references/invariants.md. For each one, how
this change could break it. If the task exercises none, say so plainly
rather than citing invariants for appearance.

## Decisions
Choices Codex must not relitigate, each with its reason in one or two
sentences.

## Interfaces
Signatures for anything crossing a layer boundary.

## Required tests
Enumerated. Each test names the invariant or failure mode it defends.

## Acceptance criteria
Observable, checkable statements. The goal is done when all of them
hold, and not before.

## Out of scope
What this task deliberately does not touch.
```

## Non-negotiables

These hold regardless of which agent is acting.

- Money is never a binary float.
- The application layer owns the transaction boundary. Not the view, not
  the domain, not the repository.
- Domain code imports no Django and no infrastructure.
- Ledger entries are append-only; corrections are compensating entries.
- Financially critical state never depends on asynchronous delivery.
- Row locks on accounts are acquired in a deterministic order.
- No test is deleted or weakened to make a change pass.

## Repository layout

```
habicapital-challenge/
  AGENTS.md         this file
  PLAN.md           per-task architecture plan (written by Claude)
  README.md
  backend/
  frontend/
  .agents/
    skills/
      safe-financial-implementation/
        SKILL.md
        references/
          architecture.md
          invariants.md
```

## Commit conventions

- One logical change per commit.
- Tests land in the same commit as the code they cover.
- Commit messages state the why, not a restatement of the diff.
