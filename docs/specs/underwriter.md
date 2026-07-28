# UNDERWRITER Journey — Implementation Spec

**Companion to:** [`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md) (v1.5), [`USER_JOURNEYS.md`](../USER_JOURNEYS.md) §3

**Audience:** an engineering agent picking up remaining UNDERWRITER-journey work with no prior session context.

---

## 1. Role & Purpose

An `UNDERWRITER` represents MFI/lender staff. **Cannot self-register** (see the platform cross-cutting spec / TDD §8 item 6) — an `ADMIN` provisions the account via `POST /admin/users`, after which the underwriter logs in through the ordinary OTP flow with no role picker shown.

## 2. Current Implementation (do not rebuild this)

**Backend**, `backend/app/modules/scoring/` (domain/application/infrastructure/presentation):
- `GET /underwriter/applicants` — paginated, backed by the anonymized `underwriter_applicant_view` (§4 of the TDD). `applicant_name`/`applicant_phone` are `NULL` until a loan's status reaches `APPROVED`/`DISBURSED`/`REPAID`. Gated `require_role("UNDERWRITER")`.
- `POST /loans` — creates a loan. For `underwriting_method: "ALGORITHMIC"`, `borrower_id` is optional and resolved server-side from `credit_score_id` — the underwriter never needs to know or supply a raw `user_id` (this is deliberate; see TDD §4/§8.1 on why the view never exposes it). Gated `require_role("UNDERWRITER")`.
- `POST /loans/{loan_id}/repayments` — records a repayment. **Exists, no frontend consumer.**
- `GET /loans/mine` — not underwriter-relevant (borrower-side).

**Frontend**, `frontend/src/features/credit-scoring/components/ApplicantTable.tsx`, rendered on `app/(dashboard)/underwriting/page.tsx`:
- Paginated applicant table (Previous/Next), risk-tier badge, "Approve" button per un-loaned applicant.
- Approval flow currently only sends `underwriting_method: "ALGORITHMIC"` and a **hardcoded `interest_rate: "0.05"`** — see Work Item 3.

## 3. Conventions to Follow

Same as the merchant spec §3. Additionally:
- **Never expose a raw `user_id` to underwriter-facing UI.** The anonymization guarantee in `underwriter_applicant_view` is a deliberate design constraint (TDD §8.1), not an oversight — any new underwriter-facing feature that seems to need a `user_id` almost certainly should be resolving it server-side the way `POST /loans` already does for `borrower_id`, not threading it through to the browser.
- `POST /loans` is gated `require_role("UNDERWRITER")` at the router level via `dependencies=[Depends(require_role("UNDERWRITER"))]` — follow this pattern (router-level `dependencies=`, not a per-handler check) for new underwriter-only endpoints.

## 4. Work Items

### 4.1 Repayment-recording UI

**Goal:** an underwriter can log a repayment against a loan they've disbursed.

**Why:** `POST /loans/{loan_id}/repayments` is fully implemented; there's no frontend for it.

**Proposed design:**
- Extend `ApplicantTable.tsx` (or split into a new `LoanDetail.tsx` if the table gets crowded) so a row with an existing loan (`a.loan_id` non-null) expands to show: current status, a "Record repayment" mini-form (amount input + submit), and a running list of past repayments for that loan.
- Repayment history needs a read endpoint — none currently exists. Add `GET /loans/{loan_id}/repayments` (paginated `Page[RepaymentOut]`) to `scoring/presentation/router.py`, backed by a new `LoanRepository.list_repayments_for_loan(loan_id, limit, offset)` (same addition needed independently in the merchant spec's Work Item 4.1 — implement it once, both journeys consume it). Gate: the loan's borrower or an `UNDERWRITER` may view it (mirror `evaluate_merchant`'s ownership-or-underwriter check).
- New hook `useLoanRepayments(loanId)` + `useRecordRepayment()` in `features/credit-scoring/api/index.ts`.

**Acceptance criteria:**
- Recording a repayment updates the visible history without a full page reload (React Query cache invalidation on the mutation, same pattern as every other mutation hook in the codebase).
- A non-underwriter, non-borrower caller gets 403 on the read endpoint.
- Repayment amount validation matches existing money-field conventions (`Decimal`, `gt=0`).

**Files likely touched:** `scoring/domain/repository.py`, `scoring/infrastructure/repository.py`, `scoring/presentation/{router,schemas}.py`, `frontend/src/features/credit-scoring/{api,components}/`.

**Coordinate with:** merchant spec Work Item 4.1 — same backend endpoint serves both journeys; don't implement it twice.

---

### 4.2 MANUAL / OVERRIDE underwriting UI

**Goal:** an underwriter can create a loan that isn't backed by an algorithmic score — either a fully manual underwriting decision, or an explicit override of what the algorithm recommended.

**Why:** the backend already supports this fully — `loans.underwriting_method IN ('ALGORITHMIC', 'MANUAL', 'OVERRIDE')`, `override_reason` column, and `CreateLoan`'s validation (`MANUAL`/`OVERRIDE` requires `override_reason`, `ALGORITHMIC` requires a resolvable `credit_score_id`) — TDD §4. The frontend only ever sends `underwriting_method: "ALGORITHMIC"`.

**Proposed design:**
- This is the one place the anonymization convention in §3 above has a real tension: a `MANUAL`/`OVERRIDE` loan has no `credit_score_id` to resolve a borrower from, so `borrower_id` **must** be supplied directly (see `CreateLoanIn`'s existing validation in `scoring/presentation/schemas.py` — this path already requires it). That means a manual-underwriting flow is inherently not anonymized the way the algorithmic path is — the underwriter is by definition making a decision about a known, named applicant (e.g. someone who walked into a branch with paperwork, not someone flowing through the app's own scoring pipeline).
- Add a distinct "Manual underwriting" panel/route (not folded into the anonymized `ApplicantTable` — the two flows have different privacy properties and shouldn't visually blend together). Fields: borrower phone number or ID lookup (needs a small admin-style user-search — reuse `GET /admin/users?role=MERCHANT` if the underwriter is meant to search by phone, though note that endpoint is currently `ADMIN`-only; either loosen it for `UNDERWRITER` read-only search or add a narrower underwriter-scoped lookup), principal, interest rate, `underwriting_method` (`MANUAL` or `OVERRIDE`), `override_reason` (required, free text).
- Backend already validates and rejects (422) a missing `override_reason` for non-`ALGORITHMIC` loans — no backend change needed for the core write path, only for the borrower-lookup question above.

**Acceptance criteria:**
- Submitting without `override_reason` for `MANUAL`/`OVERRIDE` shows the existing 422 as a field-level error, not a generic failure message.
- The resulting loan appears correctly in whatever loan-listing views exist (borrower's `GET /loans/mine`, and this journey's own view if one gets built).

**Files likely touched:** `frontend/src/features/credit-scoring/{api,components}/`, possibly `identity/presentation/admin_router.py` if the borrower-lookup question above requires loosening `GET /admin/users` access.

**Open question to resolve before implementing:** how does an underwriter identify *which* real person a manual loan is for, given the app has no general-purpose "look up a user by phone" endpoint scoped to underwriters? Resolve this product question first — don't guess an API shape for it.

---

### 4.3 Interest rate as a real underwriting input

**Goal:** replace the hardcoded `interest_rate: "0.05"` in `ApplicantTable.tsx`'s approval flow with an actual input.

**Why:** it's currently not configurable at all — every algorithmic loan gets exactly 5%, which was a placeholder, not a policy.

**Proposed design:** add an interest-rate input alongside the existing principal input in `ApplicantTable.tsx`'s per-row approval form; no backend change needed (`CreateLoanIn.interest_rate` already accepts any value). Consider a sane default (e.g. pre-fill 5%) and validate range (`Decimal(5,4)` column, so cap at a sensible max like `0.5` = 50%) client-side to match the column's precision.

**Acceptance criteria:** the rate sent in `POST /loans` matches what the underwriter actually typed, not a hardcoded constant.

**Files likely touched:** `frontend/src/features/credit-scoring/components/ApplicantTable.tsx` only.

---

## 5. Out of Scope for This Spec

- Anti-gaming / scoring-integrity concerns that affect what the underwriter sees but aren't underwriter-journey implementation gaps — tracked in the platform cross-cutting spec.
- Bulk actions (approve multiple applicants at once, bulk repayment import) — not requested, no current backend support.
