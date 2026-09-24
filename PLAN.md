# PLAN — GOAL 4: Frontend MVP

Status: awaiting implementation by Codex.

GOAL 0–3 are closed. The backend is complete: accounts, deposits, transfers
and shared expenses all work and are tested.

## Goal

A frontend that makes the product's idea obvious in thirty seconds: money
that carries context. Five screens, connected to the real API, good enough to
demo on video and defend in a pairing session.

The bar is "a coherent fintech product", not an admin panel. But scope
discipline matters more than polish: five screens, no more.

## Affected components

All under `frontend/`. The backend is **not** modified in this goal.

**New**

- `src/api/types.ts` — types mirroring the API payloads
- `src/api/client.ts` — extend: accounts, deposits, transfers, expenses
- `src/session/ActiveAccount.tsx` — context holding the selected account
- `src/components/` — `Card`, `Money`, `Button`, `Field`, `EmptyState`,
  `ErrorBanner`, `Spinner`, `AccountSwitcher`, `Avatar`
- `src/pages/Dashboard.tsx`
- `src/pages/Transfer.tsx`
- `src/pages/History.tsx`
- `src/pages/SharedExpenseDetail.tsx`
- `src/pages/CreateSharedExpense.tsx`
- `src/utils/money.ts` — COP formatting
- `src/theme/tokens.css` — extend the existing tokens

**Modified**

- `src/App.tsx` — routing and shell
- `src/index.css`

## Layer assignment

| Unit | Role |
|---|---|
| `api/` | The only place that knows URLs and response shapes. |
| `session/` | Who is the active account. |
| `pages/` | Composition and data fetching per screen. |
| `components/` | Presentational, no fetching. |
| `utils/money.ts` | Formatting only. |

No component calls `fetch` directly. Pages call the client.

## Patterns

MVC in the large: the frontend is the view, the API is the model, the pages
coordinate. No state management library — React state and context are enough
for five screens, and an interviewer asking "why Redux?" should get the answer
"because nothing here needed it".

## Invariants at risk

The frontend cannot break a financial invariant; the backend rejects bad
input regardless. But two things must hold anyway:

- **INV-6 (precision).** The frontend must never do money arithmetic in
  floating point. Amounts are integers in minor units end to end. The input
  field parses a typed COP amount into integer minor units by string
  manipulation, never `parseFloat`. Display formatting is the only conversion,
  and it is one-way.
- The UI must not imply money moved when it did not. A failed transfer shows
  the server's error; it never optimistically updates a balance.

## Decisions

1. **Five screens.** Dashboard, transfer, history, expense detail, create
   expense. Anything else is out of scope.
2. **Account switcher instead of login.** There is no auth (declared
   assumption). A control in the header picks the active account from
   `GET /api/accounts/`. The choice persists in `localStorage`, wrapped in
   try/catch, and the app works if storage is unavailable.
3. **COP formatting.** `$ 180.000` — thousands separated with `.`, no decimals
   shown when the amount is a whole peso. Minor units divide by 100 for
   display only. Use `Intl.NumberFormat("es-CO")`.
4. **The amount input is integer-only.** The user types pesos; the field
   converts to minor units with string handling. No `parseFloat` anywhere in
   `frontend/src`.
5. **Every screen handles three states explicitly**: loading, error, empty.
   Empty states say something useful, not "No data". Errors show the server's
   message and offer a retry.
6. **Context is the point, so make it visible.** In History, a transfer that
   belongs to an expense shows the expense title as a chip linking to its
   detail. An unlinked transfer looks plainly different. If a viewer cannot
   see the difference in the demo, this goal failed.
7. **Realistic demo data, in Spanish.** "Cena del viernes", "Arriendo
   noviembre", "Mercado". No lorem ipsum, no "Test User 1".
8. **Visual direction:** the existing purple/teal/neutral tokens, generous
   whitespace, rounded cards, one clear hierarchy per screen. Take layout and
   component structure ideas from
   `C:\Users\nrir\Desktop\dev\Proyectos\daily-fitness-platform` — **read only,
   never modify it** — and take none of its fitness content.
9. **Responsive down to 360px.** The dashboard and history must be usable on a
   phone. No horizontal scrolling.
10. **No new runtime dependency** beyond `react-router-dom`, which is already
    present. No UI kit, no CSS framework, no state library, no chart library.

## Screens

**Dashboard** — active account, balance in large type, primary action to
transfer, recent activity (last 5, with context chips), and the shared
expenses this account takes part in with their outstanding amount.

**Transfer** — destination account picker (handle + display name), amount,
optional shared expense selector, and a submit that shows the server's error
on failure. The idempotency key is generated client-side with
`crypto.randomUUID()` per submit attempt, and **reused if the user retries the
same submission after a network error** — that is what the key is for.

**History** — full movement list for the active account. Each row: direction,
counterparty, amount, date, and the context chip when present. Deposits are
labelled as loading balance, not as a transfer.

**Shared expense detail** — title, total, payer, participants table with
share / paid / outstanding, overall outstanding, settled state, and the
transfers linked to it.

**Create shared expense** — title, total, participant picker, payer, equal
split preview showing exactly what each person will owe **before** submitting.
The preview must match what the backend computes.

## Required checks

There is no frontend test runner yet and this goal does not add one. The gate
is:

1. `npm run build` passes with no TypeScript errors.
2. `npm run lint` passes.
3. `grep -rn "parseFloat\|Number(" frontend/src` shows no float parsing on a
   money path.
4. Manual verification of the full flow against the running backend:
   create three accounts, load balance, create "Cena del viernes" for 180.000
   among three, confirm the preview shows 60.000 each, transfer from one
   participant linked to the expense, and see the outstanding drop and the
   context chip appear in history.
5. The layout does not break at 360px width.

## Acceptance criteria

1. All five screens work against the real API. No mocked data anywhere.
2. Loading, error and empty states exist on every screen that fetches.
3. A transfer failure shows the server's message and does not alter the
   displayed balance.
4. Context is visibly distinguishable in history.
5. `npm run build` and `npm run lint` pass.
6. No new runtime dependency.

## Out of scope

- authentication, registration, sessions
- editing or deleting expenses
- pagination and search
- dark mode
- animations beyond simple transitions
- frontend unit tests
- internationalisation beyond writing the UI in Spanish

---

## FIX — review round 1

The frontend works. I verified the five screens against the live API, the
split preview matches the backend exactly including which participant
receives the leftover minor unit, and there is no float parsing anywhere.
Three changes before this goal closes.

### FIX-1 — Reformat the JSX. This is the important one.

`src/pages/SharedExpenseDetail.tsx` contains a single line of **1111
characters**. Across `frontend/src` there are 28 lines longer than 200
characters. Entire components are written as one line of JSX.

This is not a style preference. The interview for this challenge is sixty
minutes of pair programming on this code with a change I have not
anticipated, and a 1111-character line is the worst possible thing to modify
live. The apparent compactness (675 lines) is false: the code is the same
size, just unreadable.

Reformat all of `frontend/src` to conventional multi-line JSX:

- No line longer than 120 characters.
- One JSX attribute per line when an element has more than two.
- Extract deeply nested inline JSX into small named components where that
  removes nesting, but do **not** invent new abstractions just to shorten
  lines — prefer plain line breaks.
- Behaviour must not change at all. This is formatting only.

Apply the same to any backend line over 180 characters, listed by:
`find backend/src -name "*.py" | xargs awk 'length>180 {print FILENAME":"FNR}'`

### FIX-2 — Fix Spanish pluralisation

`{n} personas` renders "1 personas". Three call sites:
`CreateSharedExpense.tsx`, `Dashboard.tsx`, `SharedExpenseDetail.tsx`.
Render "1 persona" for one and "N personas" otherwise. A tiny shared helper
is fine; a full i18n library is not.

### FIX-3 — Remove `frontend/VERIFICATION.md`

Delete it. It was not requested, it sits at the frontend root where a
reviewer will trip over it, and it records environment-specific sandbox
failures ("Windows execution environment denies esbuild access") that are
artefacts of how it was produced, not facts about this project. Verification
is recorded in `docs/GOALS.md`.

### Required for this fix

- `npm run build` and `npm run lint` still pass.
- The backend suite still passes unchanged.
- No line in `frontend/src` exceeds 120 characters.
- The rendered UI is byte-for-byte equivalent in behaviour; this is a
  formatting and copy change only.
