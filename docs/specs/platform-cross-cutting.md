# Platform Cross-Cutting — Implementation Spec

**Companion to:** [`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md) (v1.5), [`USER_JOURNEYS.md`](../USER_JOURNEYS.md) (Cross-Cutting Gaps table)

**Audience:** an engineering agent picking up work that doesn't belong to one specific role journey — it spans multiple roles, or is infrastructure/production-readiness rather than a user-facing feature. If you're looking for a specific role's gaps, see `merchant.md`, `chama-member.md`, `underwriter.md`, or `admin.md` instead.

---

## 1. Scope of This Document

Four categories, roughly in priority order for a platform about to handle real money:

1. Role-based authorization gaps (ledger/chama endpoints are nav-only role-scoped today)
2. Scoring-input integrity residuals (TDD v1.5 closed the cheapest ones; these are what's left)
3. Ledger write-path robustness (concurrency on `sequence_no`)
4. Production-readiness items from the deployment section (secrets management, same-origin cookie routing) that were decided but not yet implemented, since this is still a local-dev-only build

## 2. Conventions to Follow

Same as `merchant.md` §3 — DDD layering, `Page[T]` pagination, module-specific exceptions, React Query unwrapping pattern. Additionally: **check whether a fix belongs in one bounded context's `application/` layer or genuinely needs to span modules** before writing it — most of what's below is intentionally scoped to a single module for exactly this reason (e.g. role-checking in the ledger router doesn't need to know anything about chama or scoring).

## 3. Work Items

### 3.1 Role-scope the ledger and chama endpoints

**Goal:** `POST /ledger/transactions/*`, `/ledger/products*`, and the `/chama/*` write endpoints should require the caller actually hold an appropriate role, not just "any valid login."

**Why:** today, `get_current_user` only checks that the JWT is valid — it doesn't check `role` at all on these routes. A logged-in `UNDERWRITER` or `ADMIN` account can call `POST /ledger/transactions/sale` directly (the frontend nav simply never shows them the option, which is not a security boundary). Compare to `/loans`, `/underwriter/applicants`, and all of `/admin/*`, which already use `Depends(require_role(...))` at the router level.

**Proposed design:**
- Ledger endpoints: gate to `require_role("MERCHANT")`. Check whether `CHAMA_MEMBER` should also be excluded from ledger writes entirely (currently a `CHAMA_MEMBER` has no shop, so this is a correctness fix, not just hardening) — yes, exclude them; only `MERCHANT` should reach the ledger.
- Chama endpoints: both `MERCHANT` and `CHAMA_MEMBER` should be allowed (per `USER_JOURNEYS.md` §1.4, merchants participate in chamas too) — use `require_role("MERCHANT", "CHAMA_MEMBER")` (the existing `require_role(*roles)` in `app/core/deps.py` already accepts multiple roles — no signature change needed, just apply it).
- Apply via router-level `dependencies=[Depends(require_role(...))]`, matching the established pattern in `scoring/presentation/router.py` and `identity/presentation/admin_router.py`, rather than per-handler checks.

**Acceptance criteria:**
- An `UNDERWRITER` or `ADMIN` account gets 403 on every ledger write endpoint.
- An `UNDERWRITER` or `ADMIN` account gets 403 on every chama write endpoint.
- Existing `MERCHANT`/`CHAMA_MEMBER` flows (all current tests in `tests/api/test_ledger_flow.py`, `test_chama_*.py`) continue to pass unmodified — this should be a pure tightening, not a behavior change for legitimate callers.
- Add new tests asserting the 403 for out-of-role callers, following the pattern in `tests/api/test_admin_flow.py::test_non_admin_cannot_access_admin_endpoints`.

**Files likely touched:** `ledger/presentation/router.py`, `chama/presentation/router.py`, plus new/updated tests in `tests/api/`.

---

### 3.2 Account recovery / self-service role change

**Goal:** define (this is a product decision as much as an implementation one) what happens when a user loses access to their registered phone number, and whether a user can ever request a role change themselves (today only an admin can change a role, via `PATCH /admin/users/{id}`).

**Why:** currently there is no recovery path at all — losing the phone number means losing the account permanently, with no alternate authentication factor.

**This needs a product decision before implementation, not a proposed design** — options range widely in complexity (a secondary contact method + manual verification, a KYC-document-based recovery flow, simply treating "contact support, get manually deactivated + a fresh account created" as the recovery path since `users.phone_number` is unique and the old number can't be reused otherwise). Do not implement a specific mechanism without that decision being made first.

---

### 3.3 Ledger `sequence_no` concurrency (advisory lock)

**Goal:** two simultaneous sale/expense/supplier-payment requests for the same merchant should not race on `sequence_no` allocation.

**Why:** `_AppendLedgerEntry.execute` in `ledger/application/use_cases.py` reads the last transaction, computes `sequence_no = last.sequence_no + 1`, then inserts. Two concurrent requests can both read the same "last" row before either commits. The `UNIQUE(merchant_id, sequence_no)` constraint (TDD §4) prevents a corrupted chain either way, but today the loser of that race just gets a failed request with no retry.

**Proposed design:**
- In `_AppendLedgerEntry.execute`, before reading the last transaction, take a Postgres advisory transaction lock keyed on the merchant: `SELECT pg_advisory_xact_lock(hashtext(:merchant_id))`. This serializes concurrent appends for the *same* merchant (different merchants are unaffected — `hashtext` on different UUIDs collides only astronomically rarely, and even a collision just adds unnecessary but harmless serialization between two unrelated merchants). `pg_advisory_xact_lock` auto-releases at transaction end (commit or rollback) — no explicit unlock needed, which matters here since the router commits or the whole request fails atomically either way.
- Execute this via `session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:merchant_id))"), {"merchant_id": merchant_id})` at the top of `_AppendLedgerEntry.execute`, before `get_last_transaction`.

**Acceptance criteria:**
- Two concurrent `RecordSale` calls for the same merchant never both succeed with the same `sequence_no` (already true today via the constraint) *and* neither one fails outright under normal concurrency (the actual fix — verify with a test that fires two coroutines concurrently via `asyncio.gather` against the same merchant and asserts both succeed with sequential `sequence_no` values).
- Two concurrent calls for *different* merchants are unaffected (no serialization between them) — verify this isn't accidentally globally serialized.

**Files likely touched:** `ledger/application/use_cases.py` (`_AppendLedgerEntry`), new test in `tests/integration/test_ledger_chain_trigger.py` or a new dedicated concurrency test file.

---

### 3.4 Scoring-input integrity residuals

**Goal:** close (or explicitly scope out with a decision) the gaming vectors TDD v1.5 deliberately left open.

Four distinct items, each independent — pick them up separately, don't treat this as one task:

**(a) External payment-rail corroboration.** All ledger data is self-reported. The real fix is integrating a settlement confirmation (e.g. M-Pesa Daraja API) so a `SALE` amount is checked against an actual mobile-money transaction rather than trusted as typed. **This is a significant infrastructure item** (third-party API integration, webhook handling, reconciliation logic) — do not start this without confirming which payment rail(s) the pilot actually needs to support; it's not a small addition to the existing `RecordSale` use case.

**(b) Evaluation-timing gaming.** A merchant controls exactly when `POST /scoring/evaluate/{user_id}` runs, so a fabricate-then-immediately-evaluate pattern isn't caught. Possible mitigation: rate-limit evaluations (e.g. no more than once per N hours per merchant, similar to the existing OTP rate-limiting pattern in `otp_challenges`) so a merchant can't chase a favorable instant after each burst of activity — this raises the cost of gaming without solving it outright, and is a much smaller change than (a). Needs a product decision on N before implementing.

**(c) `receivables_days` proxy gaming.** Documented in TDD §5.1 as unresolved: the feature is inferred from "next transaction with the same `customer_phone`," which is fabricable. The documented real fix is a `settles_transaction_id` link (or a dedicated `credit_repayments` table) so a repayment explicitly references the credit sale it settles, instead of being inferred. This is a schema change (new migration) plus a new `RecordRepaymentOfCreditSale`-style use case and a corresponding UI affordance on the sale-recording flow ("this is repaying an earlier credit sale" — needs a way to pick which one). Non-trivial; needs its own design pass before implementation, not just a migration.

**(d) No anomaly/fraud-risk signal for underwriters.** Nothing currently flags a suspicious pattern (sudden volume spike, implausibly smooth margin) alongside a score. A minimal version: compute a couple of simple statistical flags in `EvaluateMerchant` (e.g. "more than 80% of 30-day revenue occurred in the last 3 days," "margin_stability variance is near-zero across restocks") and include them in `CreditScore.shap_explanation`'s JSONB blob or a sibling field, surfaced in `ApplicantTable.tsx` as a warning badge. This is the cheapest of the four to prototype but is explicitly a heuristic, not a real fraud model — frame it to stakeholders as a triage aid, not a guarantee.

**Acceptance criteria (per sub-item, since they're independent):** each should ship with its own tests and its own TDD revision-notes entry, following the pattern established in v1.3/v1.4/v1.5 — don't bundle multiple of these into one change, they have different risk/effort profiles and should be reviewable independently.

---

### 3.5 Production deployment items (decided in TDD, not yet implemented)

These were resolved as design decisions in TDD §7 but the project has only ever been run in local dev — implementing them is real remaining work whenever actual deployment happens:

- **Firebase Hosting rewrite** (`/api/**` → Cloud Run) so frontend and backend are same-origin in production, which is what makes the HttpOnly/`SameSite=Strict` refresh-cookie design in §8.2 actually usable (today's bearer-token-in-localStorage is an explicitly-labeled dev-only fallback). Implementing this means: switching the frontend's token storage from `lib/auth.ts`'s localStorage functions to relying on a cookie the backend sets, and updating `/auth/otp/verify` and `/auth/refresh` to set that cookie instead of (or alongside) returning tokens in the response body. This is a meaningful auth-flow change, not just infra config — plan it as such.
- **GCP Secret Manager for the RS256 private key** — replace the local `backend/keys/jwt_private.pem` file convention with a Secret Manager-backed value injected at deploy time (`gcloud run deploy --set-secrets=...`), per TDD §7 step 5. No application code change needed if `JWT_PRIVATE_KEY_PATH` continues to point at a mounted file path — Secret Manager's Cloud Run integration mounts secrets as files, so `app/core/security.py`'s existing file-read approach should keep working unmodified. Verify this assumption when actually deploying rather than assuming it.

**These are not "implement now" items** — they only matter once a real deployment is happening. Flagging them here so they aren't lost, not requesting immediate action.

---

## 4. Suggested Priority Order

If picking work from this document without other constraints:

1. **3.1 (role-scoping)** — cheapest, highest-value, pure hardening with no product ambiguity.
2. **3.3 (advisory lock)** — small, self-contained, closes a real (if rare) correctness bug.
3. **3.4(d) (anomaly signal)** — cheapest of the scoring-integrity items, delivers underwriter-facing value without needing new infrastructure.
4. **3.2 (account recovery)** — blocked on a product decision; raise it rather than guessing.
5. **3.4(a)/(c) and 3.5** — largest, treat as separate initiatives with their own planning, not quick follow-ups.
