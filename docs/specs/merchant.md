# MERCHANT Journey — Implementation Spec

**Companion to:** [`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md) (v1.5), [`USER_JOURNEYS.md`](../USER_JOURNEYS.md) §1

**Audience:** an engineering agent picking up remaining MERCHANT-journey work with no prior session context. This spec assumes you can read the referenced files but haven't seen the conversation that produced them.

---

## 1. Role & Purpose

A `MERCHANT` runs a *duka* (retail kiosk). They self-register via OTP (no admin approval needed — see the platform cross-cutting spec for why that's deliberate). Their job in the app: record sales/expenses/inventory, and use that data to get an alternative credit score.

## 2. Current Implementation (do not rebuild this)

**Backend**, all under `backend/app/modules/ledger/` (domain/application/infrastructure/presentation) and `backend/app/modules/scoring/`:
- `POST /ledger/transactions/sale` — requires `line_items` (≥1), each referencing a product the merchant owns (403 otherwise). Idempotency-Key supported.
- `POST /ledger/transactions/expense`, `POST /ledger/transactions/supplier-payment` — Idempotency-Key supported.
- `GET /ledger/transactions` — paginated (`Page[TransactionOut]`).
- `POST /ledger/products`, `GET /ledger/products` (paginated), `POST /ledger/products/{id}/restock` (ownership-checked).
- `POST /scoring/evaluate/{user_id}`, `GET /scoring/scores/{user_id}/latest` — merchant can only evaluate/view their own score (403 for anyone else's, unless caller is `UNDERWRITER`).
- `GET /loans/mine` — paginated, **already exists, no frontend consumer yet** (see Work Item 1).

**Frontend**, `frontend/src/features/duka-ledger/` + `frontend/src/features/credit-scoring/components/MyScorePanel.tsx`, rendered on `app/(dashboard)/ledger/page.tsx`:
- `TransactionForm.tsx` — sale/expense/supplier-payment form; sale requires product + quantity picker.
- `TransactionTable.tsx` — paginated list with Previous/Next.
- `ProductPanel.tsx` — create product, restock, list with stock levels.
- `MyScorePanel.tsx` — latest score, SHAP bar breakdown, "Re-evaluate" button.

## 3. Conventions to Follow

- **DDD layering**: new backend logic goes in `domain/` (entities, repository protocols), `application/` (use cases, exceptions), `infrastructure/` (SQLAlchemy repos), `presentation/` (FastAPI router + Pydantic schemas). Look at `app/modules/ledger/application/use_cases.py` for the existing shape before adding to it.
- **Pagination**: any new list endpoint returns `app.core.pagination.Page[T]` via `PageParams = Depends()`, not a bare array. See `ListTransactions` / the `/ledger/transactions` router handler for the pattern.
- **Errors**: define a specific exception per failure mode in the module's `application/exceptions.py`, catch it in the router, map to the right HTTP status. Don't use bare `ValueError` in new code — follow `SaleRequiresLineItems` / `ProductNotOwnedByMerchant` as the template.
- **Frontend data fetching**: React Query hooks in `features/<name>/api/index.ts`, unwrapping `Page<T>.items` inside the hook so components just consume plain arrays (see `useTransactions`, `useApplicants` for the pattern, including ones that expose the full `Page` for components with Previous/Next controls).
- **Auth**: use `CurrentUser = Depends(get_current_user)` for "must be logged in," `Depends(require_role("X"))` for role-gating. Ledger/chama endpoints today only check "some valid login," not role — see the platform cross-cutting spec before assuming that's fixed.

## 4. Work Items

### 4.1 Merchant-facing loan & repayment view

**Goal:** a merchant can see their own loan(s) — status, principal, interest rate, due date — and repayment history, from `/ledger` or a new page.

**Why:** `GET /loans/mine` is fully implemented and paginated server-side; there's simply no frontend page consuming it. A merchant currently has no way to see whether they have a loan, what they owe, or its status.

**Proposed design:**
- New component `features/credit-scoring/components/MyLoansPanel.tsx` (loans already live in the `credit-scoring` feature module on the frontend — see `useMyLoans` in `features/credit-scoring/api/index.ts`, already implemented and unwrapping `Page<Loan>.items`).
- Render as a card on `/ledger` alongside `MyScorePanel`, or as its own section — a table: principal, interest rate, status badge, due date, disbursed date.
- For each loan, if `status` is `DISBURSED`, show total repaid so far. This requires either (a) a new backend aggregate endpoint (`GET /loans/{id}/repayments` returning a list or a sum), or (b) exposing repayment total on the existing `LoanOut` schema by having the router compute it. Prefer (a): add `GET /loans/{loan_id}/repayments` (paginated `Page[RepaymentOut]`) to `app/modules/scoring/presentation/router.py`, backed by a new `LoanRepository.list_repayments_for_loan(loan_id, limit, offset)` method (repository/domain protocol addition, following the same pattern as `list_for_borrower`). Gate it so only the loan's own borrower or an `UNDERWRITER` can view it (mirror the `evaluate_merchant`/`latest_score` ownership check pattern already in `scoring/presentation/router.py`).

**Acceptance criteria:**
- A merchant with no loans sees an empty state, not an error.
- A merchant with a `DISBURSED` loan sees principal, interest rate, due date, and repayment total.
- A merchant cannot view another merchant's loans or repayments (403).
- List endpoints are paginated per the existing `Page[T]` convention.

**Files likely touched:** `scoring/domain/repository.py`, `scoring/infrastructure/repository.py`, `scoring/presentation/{router,schemas}.py`, `frontend/src/features/credit-scoring/{api,components}/`, `frontend/src/app/(dashboard)/ledger/page.tsx`.

**Dependencies:** none — this is purely additive, no schema migration needed (`loan_repayments` table already exists).

---

## 5. Out of Scope for This Spec

- Role-scoping the ledger endpoints themselves beyond "must be logged in" — tracked in the platform cross-cutting spec, not merchant-specific.
- Anything about scoring-input integrity (anti-gaming) beyond what TDD v1.5 already shipped — tracked in the platform cross-cutting spec.
- A dedicated "apply for a loan" merchant-initiated flow — today only an `UNDERWRITER` creates a loan (`POST /loans`); whether merchants should be able to *request* one (as opposed to just being scored and approved) is a product decision not yet made, not an implementation gap.
