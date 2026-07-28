# Technical Design Document (TDD) & Project Specification

**Project Title:** Informal SME Digitization, Chama Ledger, and Alternative Credit Underwriting Platform

**Target Domain:** FinTech / Social Innovation (Sub-Saharan African Market)

**Deployment Target:** Google Cloud Platform (GCP Always-Free Tier)

**Version:** 1.5 (Revised)

### Revision Notes (v1.4 → v1.5)

Closes the cheapest ways to game the alternative-credit-scoring inputs on the sales/inventory and chama-punctuality sides — identified in a review of what actually stops a merchant from cooking their own books to inflate their score. **Important framing, stated explicitly here because it's a common misreading of §4's hash chain:** the append-only, tamper-evident ledger design proves a transaction wasn't edited or deleted *after* being written. It says nothing about whether the transaction was real in the first place. These fixes target that second, separate problem, and even they don't fully close it — see the "still open" list at the end of this section.

- **`POST /ledger/transactions/sale` now requires at least one line item.** Previously `line_items` was optional, meaning a merchant could record arbitrary "revenue" — `POST {"amount": "50000"}` — with zero corresponding inventory movement, directly inflating `sales_velocity` with nothing to cross-check against. A sale with no line items is now rejected (422). This is enforced in the application layer (`RecordSale`), validated *before* anything is written to the hash chain, not relied on a rollback to undo.
- **Line items (and restocks) now verify product ownership.** Neither `RecordSale` nor `RestockProduct` previously checked that a referenced `product_id` belonged to the acting merchant — a merchant could reference (and thereby decrement, or restock) another merchant's product outright. Both now reject with 403 if the product doesn't belong to the caller.
- **Chama contribution recording now enforces duty separation.** `POST /chama/contributions` previously let any authenticated user record any member's contribution, including their own — meaning a member could self-attest their own on-time payment, fabricating the `chama_punctuality` feature that feeds scoring. It now requires the acting user to (a) not be the member the contribution is credited to, and (b) hold an officer role (`CHAIRPERSON`/`TREASURER`/`SECRETARY`) within that specific chama. **Known consequence:** a chama with only one officer (e.g. freshly created, before a treasurer/secretary is added) has no one who can record that officer's own contribution — a second officer is required for that person's dues to ever be recorded by the app.
- **`margin_stability` is now windowed to the same rolling 30 days as `sales_velocity`**, instead of all-time. Previously a single burst of fabricated high-margin transactions had a permanent effect on the score, since there was no natural decay as in the other time-windowed feature.
- Frontend follow-on: the Duka Ledger sale form now requires picking a real product and quantity (previously amount-only, which would have been rejected outright by the backend fix above); the Chama Portal surfaces a clear "only an officer, not yourself" message instead of a bare failed request when the new duty-separation rule rejects a contribution.

**Still open — these gaming vectors are known and deliberately not addressed yet:**
- All of this data remains entirely self-reported. Nothing here corroborates a sale, restock, or contribution against an external source of truth (a mobile-money settlement record, a bank statement, another party's independent attestation beyond the chama-officer check above). Closing this properly means integrating a real payment rail (e.g. M-Pesa Daraja API confirmation) rather than trusting a manually-entered amount.
- The merchant still controls *when* they call `POST /scoring/evaluate/{user_id}` — nothing stops a fabricate-then-immediately-evaluate pattern within the 30-day window these fixes now bound.
- The `receivables_days` proxy (§5.1's documented gap) can still be gamed by fabricating a follow-up transaction under a made-up `customer_phone` to make a credit sale look promptly collected.
- No statistical anomaly/outlier detection exists to flag suspicious patterns (e.g. a sudden volume spike right before an evaluation, an implausibly smooth margin) to the underwriter — the score is presented as clean and final with no fraud-risk signal alongside it.

### Revision Notes (v1.3 → v1.4)

Closes a real authorization gap identified during a user-journeys review, not just a documentation drift: prior versions let **any** phone number self-register as `UNDERWRITER` at signup, which is a privilege-escalation path into the loan-approval and applicant-view endpoints — the `require_role("UNDERWRITER")` checks added in earlier versions are only as trustworthy as the role itself, and the role was entirely attacker-controlled at signup.

- Added a fourth role, `ADMIN`, to `users.role` (§4) alongside `MERCHANT`/`CHAMA_MEMBER`/`UNDERWRITER`.
- **Self-registration is now restricted to `MERCHANT`/`CHAMA_MEMBER` only.** The public OTP signup flow (`POST /auth/otp/verify` on a brand-new phone number) rejects `UNDERWRITER`/`ADMIN` outright (403). `UNDERWRITER` and `ADMIN` accounts can now only be created by an existing admin.
- Added `users.created_by` (nullable, self-referential FK) so every admin-provisioned account records who onboarded it.
- Added a full admin capability under `/admin/*` (all endpoints gated by `require_role("ADMIN")`): create a user directly with any role (this is how underwriters get onboarded — no invite step, they just log in normally afterward since the role is already set), list/filter users (paginated), update a user's name/role, and deactivate/reactivate an account.
- Added `scripts/create_admin.py` to bootstrap the very first admin account out-of-band (same pattern as `scripts/generate_jwt_keys.py`) — solves the chicken-and-egg problem of "who invites the first admin" without an open registration path.
- Fixed a related correctness bug surfaced while building this: deactivating a user (`deleted_at`) previously had no real effect on login, because `get_by_phone` (used by the OTP verify flow) already filters to active-only users — a deactivated user hitting login would be treated as brand-new and shown the registration form again, able to re-create their account. The login flow now checks for a deactivated *existing* account first and returns 403, and deactivation also revokes all of that user's outstanding refresh tokens immediately rather than waiting for them to expire naturally.
- No "reset password" equivalent was added — this is OTP-only auth with no password to reset. Deactivate covers the "lock this account out now" case; there's deliberately no separate force-logout action beyond what deactivation already does.

### Revision Notes (v1.2 → v1.3)

Findings from actually building the platform end-to-end against this spec — a mix of internal inconsistencies the implementation surfaced and gaps identified in review, all resolved here rather than left open:

- Fixed an internal contradiction between §6 (which specified a single `JWT_SECRET`) and §8.2 (which mandates RS256, an asymmetric algorithm with no single shared secret). §6's `.env.example`/compose sample now shows the actual `JWT_PRIVATE_KEY_PATH`/`JWT_PUBLIC_KEY_PATH` pattern.
- Reworded §2's architecture summary, which still said "OAuth2 with JWT (Bearer)" after §8.2 had already corrected that framing to "OTP-issued JWTs" — the two sections had drifted out of sync.
- Fixed §5.2's SHAP code sample, which did not actually run: `shap.TreeExplainer` does not support a `CalibratedClassifierCV`-wrapped model (it needs direct access to raw tree structure; `CalibratedClassifierCV` holds several per-fold calibrated copies of the base estimator internally, not one tree to introspect). Replaced with the model-agnostic `shap.Explainer(model.predict_proba, background)`, which works for any estimator, calibrated or not.
- Added the `identity` bounded context to §3.2 — `users`, `refresh_tokens`, and `otp_challenges` had no owning module in the original three-context layout (`ledger`, `chama`, `scoring`).
- Documented, in §4 and §8.1, how `POST /loans` resolves `borrower_id` server-side from `credit_score_id` for `ALGORITHMIC` loans. The anonymized `underwriter_applicant_view` never exposes a raw `user_id` by design, but loan creation requires one; this was previously an implicit implementation detail rather than a stated design decision.
- Flagged, in §5.1, that "Receivables Days" cannot be computed as specified against the current schema — there is no event linking a credit sale to its later repayment, only `is_credit = TRUE` on the original sale. Documented the interim proxy (treating the next transaction from the same `customer_phone` as an implicit repayment signal) and what a correct fix looks like (a `settles_transaction_id` link or dedicated repayment table) before this feature is trusted for a real lending decision.
- Resolved the tension between §8.2's HttpOnly/`SameSite=Strict` refresh-cookie design and §7's deployment topology, where the frontend (Firebase App Hosting) and backend (Cloud Run) sit on different Google-managed domains by default and are therefore not same-site. §7 now specifies a Firebase Hosting rewrite (`/api/**` → the Cloud Run service) so the backend is served from the same origin as the frontend in production, which is what makes the cookie design in §8.2 actually work. Local dev keeps a bearer-token fallback as an explicitly-labeled exception, not the production design.
- Added a secrets-management note to §7: the RS256 private key needs to live in GCP Secret Manager for the Cloud Run deployment, not baked into the image or left as a bare file — this was previously unaddressed for a stateless, scale-to-zero service.
- Added a concurrency note to §4: two simultaneous writes for the same merchant can race on `sequence_no` allocation. The `UNIQUE(merchant_id, sequence_no)` constraint prevents corruption but the loser currently just fails; recommended a Postgres advisory lock keyed on `merchant_id` around the read-last-sequence-then-insert step as the fix, tracked for implementation.
- Added `Idempotency-Key` support (§4, §8) on the ledger's sale/expense/supplier-payment write endpoints, backed by a new `idempotency_keys` table — a client retry after a timed-out request now replays the original response instead of creating a second real transaction.
- Added limit/offset pagination (§4, new §8.5) to every list endpoint (`GET /ledger/transactions`, `/ledger/products`, `/chama/groups`, `/chama/groups/{id}/members`, `/loans/mine`, `/underwriter/applicants`) — previously unbounded, which directly worked against §7.1's own capacity-planning premise that this ledger grows without deletion.

### Revision Notes (v1.1 → v1.2)

- Added an `INSERT`-time trigger on `duka_transactions` that validates `previous_hash` against the prior row's `record_hash` for that merchant — v1.1 only blocked `UPDATE`/`DELETE`, but nothing stopped a buggy or malicious insert from writing a broken chain link in the first place.
- Added a trigger to keep `products.quantity_on_hand` in sync with `inventory_movements`, since relying on the application layer to always wrap both writes in one transaction was a silent-drift risk.
- Added `UNIQUE (member_id, cycle_due_date)` on `chama_contributions` to stop duplicate rows from corrupting the punctuality feature.
- Made `loans.credit_score_id` nullable and added `underwriting_method` + `override_reason` to support manually-underwritten or overridden loans, not just algorithmically-scored ones.
- Redesigned the ML scoring cache key to bucket continuous features before hashing, since hashing raw floats meant the cache almost never hit in practice.
- Added a note on replacing the linear PD→score mapping with a PDO (points-to-double-odds) log-odds scaling once real default data exists.
- Added a note on the demographic-data gap for disparate-impact testing (§5 mentions checking gender/region, but the schema never collects either) and the Data Protection Act implications of collecting it.
- Added a §7 capacity-planning subsection sizing how long the ledger's append-only, never-deleted rows can live inside a 500MB free-tier Postgres instance, plus an archiving/partitioning plan for when it doesn't fit.
- Added OTP abuse protection (rate limiting, backoff, SIM-swap-aware re-auth) and explicit refresh-token rotation behavior to §8.
- Added an ODPC (Office of the Data Protection Commissioner) data-controller registration checkbox alongside the existing CBK licensing note in §8.4.

---

## 1. Executive Summary & Research Justification

### 1.1 Problem Statement

Across Sub-Saharan Africa, small and medium-sized enterprises (MSMEs) represent roughly 40% of GDP and employ over 60% of the workforce. However, over 80% of urban commerce occurs within the informal economy. Small merchants (*Dukas* or retail kiosks) and community savings circles (*Chamas*) rely heavily on cash transactions and paper ledgers.

Because these businesses lack formal accounting records and traditional bank statements, they remain "credit invisible" to commercial financial institutions. This creates an estimated **$331 billion SME credit gap** in Sub-Saharan Africa — a figure originally estimated by the IFC in 2018. More recent African Development Bank analysis puts the continent-wide SME financing gap as high as $421 billion annually, suggesting the true current figure for Sub-Saharan Africa alone is likely higher than $331B today. Either way, the gap forces shopkeepers to rely on high-interest informal lenders or forgo growth opportunities entirely.

### 1.2 Proposed Solution

This web application digitizes informal financial activities into verifiable digital records and applies machine learning to evaluate credit risk using non-traditional data.

1. **Duka Digital POS & Ledger:** Allows merchants to record daily cash/credit sales, manage inventory, and issue digital receipts (via WhatsApp/SMS API).
2. **Chama Savings Portal:** Digitizes group contributions, rotation schedules (Merry-Go-Round), and social guarantees.
3. **Alternative Credit Scoring Engine:** Aggregates transaction velocity, contribution punctuality, and inventory turnover to generate a credit score (300–850) powered by **Explainable AI (SHAP)**.
4. **Underwriter Portal:** Provides micro-finance institutions (MFIs) with an anonymized dashboard to evaluate credit risk and disburse micro-loans.

---

## 2. System Architecture Blueprint

The system follows a decoupled, cloud-native architecture combining a **Feature-Driven Next.js 16 frontend** and a **Domain-Driven Design (DDD) FastAPI backend**, orchestrated via Docker containers.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                                  │
│                   Next.js 16 (App Router) + pnpm                             │
│       [Duka Ledger]      [Chama Portal]      [Underwriter Dashboard]         │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ HTTPS / REST API / WebSockets
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                             API GATEWAY & AUTH                               │
│           OTP-Issued JWTs (RS256, Bearer) + CORS Middleware                  │
│           (v1.3: reworded from "OAuth2" -- see §8.2 for why)                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND SERVICE                             │
│                  Domain-Driven Design (Bounded Contexts)                     │
│  ┌───────────────────────┐ ┌────────────────────────┐ ┌───────────────────┐  │
│  │ Merchant Ledger Module │ │  Chama Management Mod. │ │  Credit Scoring   │  │
│  │   (Double-Entry Log)  │ │ (Group Rotation Engine)│ │  (ML + SHAP XAI)  │  │
│  └───────────┬───────────┘ └───────────┬────────────┘ └─────────┬─────────┘  │
└──────────────┼─────────────────────────┼────────────────────────┼────────────┘
               │                         │                        │
               ▼                         ▼                        ▼
┌──────────────────────────────────┐            ┌──────────────────────────────┐
│      PostgreSQL (Database)       │            │         Redis Cache          │
│   (ACID Ledger + Audit Trails)   │            │   (Session & Scoring Cache)  │
└──────────────────────────────────┘            └──────────────────────────────┘

```

### 2.1 Implementation Notes (v1.1)

- **"API Gateway" is FastAPI middleware, not a separate service.** At this scale, running a dedicated gateway (Cloud Endpoints/Apigee) adds cost and latency for no real benefit — the box in the diagram is ASGI middleware (CORS, JWT verification, rate limiting) inside the same FastAPI service. Revisit if/when multiple backend services need a shared entry point.
- **Async work must not block the request/response cycle.** Sending WhatsApp/SMS receipts is I/O-bound and shouldn't run inline on a Cloud Run request thread. Use FastAPI `BackgroundTasks` for the MVP; move to Cloud Tasks or Pub/Sub once volume justifies it.
- **WebSockets on Cloud Run have real constraints:** connections cap out at 60 minutes and an open socket prevents the instance from scaling to zero, which works against the "Always-Free" goal. For the free-tier MVP, prefer polling or Server-Sent Events for live updates (e.g. underwriter dashboard refresh) and reserve WebSockets for a later stage where `min-instances ≥ 1` is already budgeted for.

---

## 3. Directory Layout & Architectural Patterns

### 3.1 Next.js 16 Feature-Driven Frontend

Routing is decoupled from business logic. The `app/` directory handles routes, while `features/` isolates business components:

```text
frontend/
├── src/
│   ├── app/                         # Route Handlers (Routing Shells Only)
│   │   ├── (dashboard)/
│   │   │   ├── ledger/page.tsx
│   │   │   ├── chama/page.tsx
│   │   │   └── underwriting/page.tsx
│   │   └── layout.tsx
│   ├── features/                    # Feature Modules
│   │   ├── duka-ledger/             # Isolated Feature: Sales, Stock, Receipts
│   │   │   ├── api/                 # React Query / Fetch calls
│   │   │   ├── components/          # Feature UI Components
│   │   │   ├── hooks/               # Custom React hooks
│   │   │   └── types/               # TypeScript interfaces
│   │   ├── chama-portal/            # Isolated Feature: Group Savings
│   │   └── credit-scoring/          # Isolated Feature: Underwriter Charts
│   ├── components/ui/               # Shared Reusable UI (shadcn/ui)
│   └── lib/                         # Global Utilities & API Clients
├── tests/                           # Component & integration tests
├── Dockerfile.dev                   # Hot-reloading Docker setup
├── Dockerfile                       # Multi-stage production Docker build
└── pnpm-lock.yaml

```

### 3.2 FastAPI Domain-Driven Design (DDD) Backend

Organized into Bounded Contexts. Each module isolates Domain rules from Infrastructure and HTTP handlers:

```text
backend/
├── app/
│   ├── core/                        # Global Config, DB Engine, Security
│   ├── modules/                     # BOUNDED CONTEXTS
│   │   ├── identity/                 # Context 1: Users, OTP Auth, Refresh Tokens (NEW v1.3 --
│   │   │                             # users/refresh_tokens/otp_challenges had no owning module before).
│   │   │                             # Also owns admin user-provisioning/management (NEW v1.4).
│   │   ├── ledger/                  # Context 2: Merchant Sales & Stock
│   │   │   ├── domain/              # Entities, Value Objects, Repository Interfaces
│   │   │   ├── application/         # Use Cases, Command Handlers
│   │   │   ├── infrastructure/      # SQLAlchemy ORM Models, DB Repositories
│   │   │   └── presentation/        # FastAPI Routers, Pydantic Schemas
│   │   ├── chama/                   # Context 3: Group Ledger & Rotation
│   │   └── scoring/                 # Context 4: Credit ML Engine & SHAP
│   └── main.py                      # FastAPI App Initialization
├── alembic/                         # Versioned schema migrations (required — see §4)
├── tests/                           # Unit & integration tests per bounded context
├── Dockerfile
└── requirements.txt

```

---

## 4. Database Schema & Ledger Integrity

Financial records require append-only immutability. This is enforced three ways: an `INSERT`-time trigger validates that each new row's `previous_hash` correctly links to the prior row (catching broken chains the moment they're written, not just when someone later audits them), a `BEFORE UPDATE OR DELETE` trigger rejects any mutation outright, and a SHA-256 hash chain gives **external** auditors/MFI partners a way to independently verify integrity without DB access. Schema changes should be applied through Alembic migrations, not run ad hoc against production.

> `gen_random_uuid()` is native to PostgreSQL 13+ (this stack runs 16-alpine), so no `uuid-ossp` extension is required — the earlier draft declared it but never used it.

```sql
-- =====================================================================
-- USERS & SESSIONS
-- =====================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('MERCHANT', 'CHAMA_MEMBER', 'UNDERWRITER', 'ADMIN')), -- ADMIN added v1.4
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE, -- soft delete: preserves ledger FK integrity and
                                          -- supports Data Protection Act erasure requests
                                          -- via PII redaction instead of row deletion
    created_by UUID REFERENCES users(id) ON DELETE SET NULL, -- NEW v1.4: set when an admin provisions
                                                                -- this account directly (UNDERWRITER/ADMIN
                                                                -- onboarding); NULL for self-registered
                                                                -- MERCHANT/CHAMA_MEMBER accounts
    CONSTRAINT chk_deleted_after_created CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);
CREATE INDEX idx_users_active ON users(id) WHERE deleted_at IS NULL;

-- NEW (v1.4): self-registration (the public OTP signup flow) only ever
-- creates MERCHANT/CHAMA_MEMBER accounts -- enforced in the application
-- layer (VerifyOtp), not by a DB constraint, since the DB has no notion of
-- "who is calling" to distinguish self-signup from admin-provisioned
-- creation. UNDERWRITER/ADMIN accounts are created exclusively via
-- POST /admin/users (or scripts/create_admin.py for the very first admin).

-- Backs the HttpOnly refresh-cookie flow described in §8. Rotation semantics
-- (single-use, replaced on each refresh) are enforced at the application
-- layer -- see §8.2.
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    token_hash VARCHAR(128) NOT NULL, -- store a hash, never the raw token
    replaced_by UUID REFERENCES refresh_tokens(id), -- set when rotated; a non-null value on an
                                                      -- otherwise-unrevoked token is itself a
                                                      -- reuse-detection signal (see §8.2)
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id) WHERE revoked_at IS NULL;

-- Backs OTP rate limiting / backoff in §8.2. A short-lived table by design --
-- rows are only relevant for the current or recent OTP challenge window.
CREATE TABLE otp_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) NOT NULL,
    code_hash VARCHAR(128) NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    consumed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_otp_phone_recent ON otp_challenges(phone_number, created_at DESC);

-- =====================================================================
-- MERCHANT DUKA LEDGER (Immutable, Append-Only)
-- =====================================================================

CREATE TABLE duka_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, -- never CASCADE on ledger data
    sequence_no BIGINT NOT NULL,          -- monotonic per-merchant counter; makes gaps/reordering detectable
    amount DECIMAL(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'KES',
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('SALE', 'EXPENSE', 'SUPPLIER_PAYMENT')),
    is_credit BOOLEAN DEFAULT FALSE,
    customer_phone VARCHAR(20),
    previous_hash VARCHAR(64) NOT NULL,   -- '0' repeated 64 times for a merchant's first transaction (genesis)
    record_hash VARCHAR(64) NOT NULL,     -- SHA256(previous_hash || merchant_id || sequence_no || amount || currency || created_at)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP, -- the app should pass this value
                                                                              -- explicitly so the hashed value
                                                                              -- matches what's actually stored
    UNIQUE (merchant_id, sequence_no)
);

CREATE INDEX idx_ledger_merchant ON duka_transactions(merchant_id, created_at DESC);
CREATE INDEX idx_ledger_customer ON duka_transactions(customer_phone) WHERE customer_phone IS NOT NULL;

-- True immutability at the DB layer -- the hash chain alone only lets you
-- *detect* tampering after the fact if someone verifies it.
CREATE OR REPLACE FUNCTION prevent_ledger_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'duka_transactions is append-only: % is not permitted', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_no_update_ledger
    BEFORE UPDATE OR DELETE ON duka_transactions
    FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation();

-- NEW (v1.2): validate the chain link at write time instead of only being
-- able to detect a broken chain later by walking it. Confirms this row's
-- previous_hash matches the record_hash of the immediately preceding row
-- for the same merchant (or the genesis value, for sequence_no = 1).
CREATE OR REPLACE FUNCTION validate_ledger_chain() RETURNS TRIGGER AS $$
DECLARE
    expected_prev_hash VARCHAR(64);
BEGIN
    IF NEW.sequence_no = 1 THEN
        expected_prev_hash := repeat('0', 64);
    ELSE
        SELECT record_hash INTO expected_prev_hash
        FROM duka_transactions
        WHERE merchant_id = NEW.merchant_id AND sequence_no = NEW.sequence_no - 1;

        IF expected_prev_hash IS NULL THEN
            RAISE EXCEPTION 'duka_transactions chain gap: merchant % has no row at sequence_no %',
                NEW.merchant_id, NEW.sequence_no - 1;
        END IF;
    END IF;

    IF NEW.previous_hash IS DISTINCT FROM expected_prev_hash THEN
        RAISE EXCEPTION 'duka_transactions chain break: merchant % sequence_no % previous_hash mismatch',
            NEW.merchant_id, NEW.sequence_no;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_ledger_chain
    BEFORE INSERT ON duka_transactions
    FOR EACH ROW EXECUTE FUNCTION validate_ledger_chain();

-- =====================================================================
-- INVENTORY (feeds the "Margin Stability" / turnover scoring features in §5)
-- =====================================================================

-- v1.5: a SALE against duka_transactions must reference at least one
-- inventory_movements row here via a real, merchant-owned product_id --
-- application-layer checks, not new columns/constraints (see §8).

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    unit_cost DECIMAL(12, 2) NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_threshold INT DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_products_merchant ON products(merchant_id);

CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    duka_transaction_id UUID REFERENCES duka_transactions(id) ON DELETE RESTRICT,
    quantity_delta INT NOT NULL, -- negative for a sale, positive for a restock
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_inventory_movements_product ON inventory_movements(product_id, created_at DESC);

-- NEW (v1.2): v1.1 relied on the application layer wrapping a movement
-- insert and a products.quantity_on_hand update in the same transaction.
-- That's a silent-drift risk the moment any code path (a retry, a partial
-- failure, a future admin script) skips it. This trigger makes the DB the
-- single source of truth for stock level instead.
CREATE OR REPLACE FUNCTION apply_inventory_movement() RETURNS TRIGGER AS $$
BEGIN
    UPDATE products
    SET quantity_on_hand = quantity_on_hand + NEW.quantity_delta,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.product_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_apply_inventory_movement
    AFTER INSERT ON inventory_movements
    FOR EACH ROW EXECUTE FUNCTION apply_inventory_movement();
-- Note: products.quantity_on_hand >= 0 CHECK (above) still guards against
-- oversell -- an insert that would drive stock negative fails the whole
-- transaction, including the movement row itself.

-- =====================================================================
-- CHAMA GROUP SAVINGS
-- =====================================================================

CREATE TABLE chama_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_name VARCHAR(100) NOT NULL,
    contribution_cycle VARCHAR(20) NOT NULL CHECK (contribution_cycle IN ('WEEKLY', 'MONTHLY')),
    cycle_amount DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chama_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    member_role VARCHAR(20) NOT NULL DEFAULT 'MEMBER'
        CHECK (member_role IN ('CHAIRPERSON', 'TREASURER', 'SECRETARY', 'MEMBER')), -- the three non-MEMBER
                                                                                     -- roles are who's allowed to
                                                                                     -- record a contribution for
                                                                                     -- someone else (v1.5, §8)
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chama_id, user_id)
);

-- This is what "Chama Punctuality" (§5.1) is actually computed from --
-- the v1.0 schema listed the feature but had nowhere to source it from.
CREATE TABLE chama_contributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    member_id UUID NOT NULL REFERENCES chama_members(id) ON DELETE RESTRICT,
    cycle_due_date DATE NOT NULL,
    amount_due DECIMAL(12, 2) NOT NULL,
    amount_paid DECIMAL(12, 2) NOT NULL DEFAULT 0,
    paid_at TIMESTAMP WITH TIME ZONE,
    is_on_time BOOLEAN, -- set by the application when payment is recorded:
                         -- paid_at::date <= cycle_due_date. (Deliberately not a
                         -- generated column: a timestamptz->date cast is timezone-
                         -- dependent, which Postgres won't allow in a STORED
                         -- generated expression.)
    UNIQUE (member_id, cycle_due_date) -- NEW (v1.2): one contribution row per member
                                        -- per cycle. Without this, a duplicate insert
                                        -- (retry, double-submit) silently corrupts the
                                        -- punctuality feature by inflating the
                                        -- denominator or numerator.
);
CREATE INDEX idx_chama_contrib_member ON chama_contributions(member_id, cycle_due_date DESC);

-- Merry-go-round payout tracking
CREATE TABLE chama_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    recipient_member_id UUID NOT NULL REFERENCES chama_members(id) ON DELETE RESTRICT,
    payout_amount DECIMAL(12, 2) NOT NULL,
    scheduled_date DATE NOT NULL,
    paid_out_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================================
-- CREDIT SCORING & LOANS
-- =====================================================================

CREATE TABLE credit_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    credit_score INT NOT NULL CHECK (credit_score BETWEEN 300 AND 850),
    recommended_limit DECIMAL(12, 2) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH')),
    model_version VARCHAR(30) NOT NULL,   -- e.g. 'rf_v3_2026_06' -- required to reproduce or
                                           -- audit any past lending decision
    shap_explanation JSONB NOT NULL,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_scoring_user ON credit_scores(user_id, evaluated_at DESC);

-- v1.0 had no schema for the product's actual purpose: disbursing loans.
-- v1.2: credit_score_id is now nullable, since not every loan in a real
-- underwriting operation originates from an algorithmic score -- a manually
-- underwritten loan, or a human override of a score, needs a place to live too.
CREATE TABLE loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borrower_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    credit_score_id UUID REFERENCES credit_scores(id) ON DELETE RESTRICT, -- nullable (v1.2);
                                                                            -- ties every algorithmically-
                                                                            -- scored loan to the score
                                                                            -- that justified it
    underwriting_method VARCHAR(20) NOT NULL DEFAULT 'ALGORITHMIC'
        CHECK (underwriting_method IN ('ALGORITHMIC', 'MANUAL', 'OVERRIDE')),
    override_reason TEXT, -- required by application logic (not a DB constraint, to keep
                           -- migrations simple) whenever underwriting_method <> 'ALGORITHMIC'
    principal DECIMAL(12, 2) NOT NULL,
    interest_rate DECIMAL(5, 4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'DISBURSED', 'REPAID', 'DEFAULTED', 'REJECTED')),
    disbursed_at TIMESTAMP WITH TIME ZONE,
    due_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_algorithmic_has_score
        CHECK (underwriting_method <> 'ALGORITHMIC' OR credit_score_id IS NOT NULL)
);

CREATE TABLE loan_repayments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE RESTRICT,
    amount DECIMAL(12, 2) NOT NULL,
    paid_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_loan_repayments_loan ON loan_repayments(loan_id, paid_at DESC);

-- =====================================================================
-- IDEMPOTENCY (NEW v1.3) -- backs Idempotency-Key support on the ledger's
-- write endpoints. A client retry after a timed-out sale/expense/supplier-
-- payment request must not create a second real transaction.
-- =====================================================================

CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(128) NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    response_status INT NOT NULL,
    response_body JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, idempotency_key, endpoint) -- also serves as the lookup index
);

-- =====================================================================
-- ANONYMIZED UNDERWRITER READ MODEL (implements §8.1's PII-masking claim)
-- =====================================================================

-- Underwriters query this view, never the base tables directly. Applicant
-- identity stays NULL until a loan's status moves past pre-approval.
CREATE VIEW underwriter_applicant_view AS
SELECT
    cs.id AS credit_score_id,
    l.id AS loan_id,
    cs.credit_score,
    cs.risk_tier,
    cs.recommended_limit,
    cs.shap_explanation,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.full_name ELSE NULL END AS applicant_name,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.phone_number ELSE NULL END AS applicant_phone,
    l.status
FROM credit_scores cs
JOIN users u ON u.id = cs.user_id
LEFT JOIN loans l ON l.credit_score_id = cs.id;
```

**Access control to pair with this schema:** the application's database role should hold `INSERT, SELECT` only on `duka_transactions`, `chama_contributions`, and `loan_repayments` — no application-facing role should have `UPDATE`/`DELETE` grants on ledger tables. Reserve a separate, more privileged role, used only for compliance-driven PII redaction, and log every use of it.

**Pagination (NEW v1.3):** every list endpoint reading from these tables (`GET /ledger/transactions`, `/ledger/products`, `/chama/groups`, `/chama/groups/{id}/members`, `/loans/mine`, `/underwriter/applicants`) takes `limit`/`offset` query params (default 50, capped at 200) and returns `{items, total, limit, offset}` rather than a bare array. This was a gap in earlier versions that directly worked against §7.1's own premise — an append-only, never-deleted ledger will eventually make an unpaginated list endpoint slow regardless of how well the rest of the schema is designed. The existing `idx_ledger_merchant`, `idx_chama_contrib_member`, etc. indexes (all `(foreign_key, timestamp DESC)`) already make the offset scan cheap at pilot scale; revisit with cursor-based pagination only if offset costs become measurable at higher volume.

**Concurrency on `sequence_no` (NEW v1.3):** two simultaneous sale/expense/supplier-payment requests for the same merchant can race on reading the last `sequence_no` before either commits. The `UNIQUE(merchant_id, sequence_no)` constraint above prevents a corrupted chain either way, but today the loser of that race simply gets a failed request rather than a transparent retry. Recommended fix, not yet implemented: take a Postgres advisory lock keyed on `merchant_id` (`pg_advisory_xact_lock(hashtext(merchant_id))`) around the read-last-then-insert sequence in the application layer, scoped to the transaction so it releases automatically on commit/rollback.

**Anonymized view vs. loan creation (NEW v1.3):** `underwriter_applicant_view` deliberately never exposes a raw `user_id` — by design, per §8.1, only `credit_score_id` and (post-approval) name/phone. But creating a loan requires `loans.borrower_id`. `POST /loans` resolves this server-side: when `credit_score_id` is supplied and `borrower_id` is not, the backend looks up `credit_scores.user_id` for that score internally and uses it as the borrower — the underwriter's browser never needs to see or supply a raw user ID for an `ALGORITHMIC` loan. `MANUAL`/`OVERRIDE` loans (no score backing them) still require `borrower_id` supplied directly, since there's no score row to resolve it from in that case.

---

## 5. Machine Learning & Alternative Scoring Pipeline

### 5.1 Alternative Feature Matrix

The model transforms non-traditional operational metrics into credit predictors:

| Metric | Category | Formula / Calculation | Expected Signal | Sourced From |
| --- | --- | --- | --- | --- |
| **Sales Velocity** | Duka Ledger | $\frac{\text{Total Revenue 30D}}{\text{Active Business Days}}$ | Revenue consistency & cash flow capacity. | `duka_transactions` |
| **Receivables Days** | Customer Credit | $\text{Avg Days to Collect Customer Debt}$ | Debt recovery discipline & working capital risk. | `duka_transactions` (`is_credit`) |
| **Chama Punctuality** | Chama Portal | $\frac{\text{On-Time Contributions}}{\text{Total Cycles Held}} \times 100$ | Social accountability & repayment willingness. | `chama_contributions` |
| **Margin Stability** | Inventory | $\frac{\text{Gross Profit}}{\text{Total Revenue}}$ | Business profitability & pricing power. | `products`, `inventory_movements` |

> **Gap (NEW v1.3):** "Receivables Days" isn't actually computable as specified against §4's schema. A credit sale is only `duka_transactions.is_credit = TRUE` on the original row — there is no event representing "this credit sale was repaid," so there's nothing to measure days-to-collect *against*. The current implementation uses a proxy: treat the next transaction from the same `customer_phone` as an implicit repayment signal, and measure the gap to that (or to now, if none exists yet). That's a reasonable stopgap for a pilot scoring on synthetic data, but it's a guess, not what the formula claims to measure. Before this feature backs a real lending decision, add an explicit link from a repayment back to the credit sale it settles (e.g. a `settles_transaction_id` FK on `duka_transactions`, or a dedicated `credit_repayments` table) so the metric means what it says.

### 5.2 Python Scoring & SHAP Implementation

```python
# app/modules/scoring/domain/scoring_engine.py
import hashlib
import json
from typing import Dict, Tuple

import joblib
import pandas as pd
import shap
from pydantic import BaseModel, Field

MODEL_VERSION = "rf_v3_2026_06"   # bump this and re-deploy whenever the model is retrained;
                                   # this is what credit_scores.model_version traces back to
CACHE_TTL_SECONDS = 60 * 60 * 6   # fallback TTL; prefer explicit invalidation (see note below)

# NEW (v1.2): bucket widths used to build the cache key. Hashing raw floats
# meant the cache key changed on every request (sales_velocity to the cent
# essentially never repeats), so the cache almost never hit in practice.
# Bucketing collapses "close enough" feature vectors onto the same key --
# tune bucket width against how much score drift is acceptable for a cache
# hit; these defaults trade a small amount of score staleness for a much
# higher hit rate.
BUCKET_WIDTHS = {
    "sales_velocity": 50.0,       # nearest 50 KES/day
    "receivables_days": 1.0,      # nearest day
    "chama_punctuality": 5.0,     # nearest 5 percentage points
    "margin_stability": 0.02,     # nearest 2 percentage points
}


class MerchantFeatures(BaseModel):
    """Strict schema for scoring inputs. Prevents a missing/mistyped feature name
    from silently producing a NaN instead of an error, and is the single source of
    truth for what the model expects -- keep it in lockstep with the training
    feature list, not just with whatever the DB happens to return."""
    sales_velocity: float = Field(ge=0)
    receivables_days: float = Field(ge=0)
    chama_punctuality: float = Field(ge=0, le=100)
    margin_stability: float = Field(ge=0, le=1)

    def bucketed(self) -> Dict[str, float]:
        """Round each feature to its bucket width for cache-key purposes only.
        The unbucketed values are still what's actually scored."""
        return {
            name: round(value / BUCKET_WIDTHS[name]) * BUCKET_WIDTHS[name]
            for name, value in self.model_dump().items()
        }


class AlternativeCreditScorer:
    def __init__(self, model_path: str, redis_client=None):
        # The model artifact at model_path should already be wrapped in
        # sklearn's CalibratedClassifierCV (isotonic or sigmoid) at training
        # time. predict_proba() on a raw RandomForest/XGBoost classifier is
        # NOT a calibrated probability -- feeding an uncalibrated score into
        # the PD -> credit_score mapping below produces scores that look
        # precise but aren't defensible to an underwriter or regulator.
        #
        # FIXED (v1.3): the artifact bundles a small background sample
        # alongside the model -- {"model": ..., "feature_names": [...],
        # "background": df} -- because shap.TreeExplainer does NOT support a
        # CalibratedClassifierCV-wrapped model (it needs direct access to raw
        # tree structure; CalibratedClassifierCV holds several per-fold
        # calibrated copies of the base estimator internally, not one tree to
        # introspect -- the v1.2 snippet here did not actually run). The
        # model-agnostic shap.Explainer over predict_proba works for any
        # estimator, calibrated or not, at the cost of being slower than
        # TreeExplainer -- acceptable since scoring is cached and not on a
        # hot path.
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact["feature_names"]
        self.explainer = shap.Explainer(self.model.predict_proba, artifact["background"])
        self.redis = redis_client

    def evaluate_merchant(
        self, user_id: str, features: MerchantFeatures
    ) -> Tuple[int, str, Dict[str, float]]:
        """
        Calculates credit score (300-850), risk tier, and SHAP explainability values.
        """
        # NEW (v1.2): cache key built from bucketed features, not raw ones.
        bucketed = features.bucketed()
        cache_key = (
            f"score:{user_id}:{MODEL_VERSION}:"
            f"{hashlib.sha256(json.dumps(bucketed, sort_keys=True).encode()).hexdigest()[:16]}"
        )
        if self.redis is not None:
            cached = self.redis.get(cache_key)
            if cached:
                return tuple(json.loads(cached))

        df = pd.DataFrame([features.model_dump()])  # score on the true, unbucketed values

        # 1. Predict Default Probability (PD)
        pd_score = self.model.predict_proba(df)[0][1]

        # 2. Map PD to Credit Score Range (300 to 850).
        # NOTE (v1.2): this linear mapping is a placeholder suitable for a
        # pilot with no real default history yet. Once actual default data
        # exists, replace it with a proper PDO (points-to-double-odds)
        # log-odds scaling -- the standard scorecard approach -- which
        # requires calibrating a base score, base odds, and PDO constant
        # against observed default rates rather than an arbitrary linear
        # coefficient (550) chosen without reference to real outcomes.
        credit_score = int(850 - (pd_score * 550))

        # 3. Classify Risk Tier
        if credit_score >= 720:
            risk_tier = "LOW"
        elif credit_score >= 600:
            risk_tier = "MEDIUM"
        else:
            risk_tier = "HIGH"

        # 4. Compute SHAP Values for XAI (Explainable AI)
        explanation = self.explainer(df)
        values = explanation.values[0]
        if values.ndim == 2:
            # predict_proba has 2 output columns (class 0, class 1); keep the
            # contribution to the "default" (class 1) probability.
            values = values[:, 1]
        shap_dict = dict(zip(self.feature_names, (float(v) for v in values)))

        result = (credit_score, risk_tier, shap_dict)
        if self.redis is not None:
            self.redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
        return result
```

**Cache invalidation:** don't just rely on the TTL — invalidate a merchant's cached score whenever a new `duka_transactions` or `chama_contributions` row is written for them. A stale six-hour-old score defeats the point of scoring on live behavioral data. Bucketing (above) increases hit rate for repeat lookups within a short window, but a fresh underlying event should still evict the key outright rather than wait on the bucket to shift.

**Before this scores a real lending decision:**
- Backtest the calibration curve against held-out data, and replace the linear PD→score mapping with a PDO-scaled one once real defaults exist (see note in code above).
- Run a disparate-impact check across at least gender and region. **Gap to close first:** the current schema (§4) doesn't collect either attribute, so this check can't be run yet as written. Two paths forward, each with different Data Protection Act, 2019 implications: (a) collect gender/region as explicit, consent-gated fields on `users` — the more defensible option for a real fairness audit, since proxy inference (b) risks getting the classification itself wrong while still processing sensitive personal data under the Act's special-category rules; or (b) use geographic/behavioral proxies (e.g. `chama_groups` location, phone number prefix) for a coarser analysis without collecting the attribute directly, accepting weaker statistical power. This needs a decision — and, for option (a), a defined lawful basis and consent flow — before the underwriter portal handles real money.
- Make sure every deployed model bumps `MODEL_VERSION` so any historical score can be traced to the exact model that produced it.

---

## 6. Containerization & Local Development Setup

To support hot-reloading for both Next.js 16 (with `pnpm`) and FastAPI during development, run the setup using Docker Compose. Secrets are read from a local, gitignored `.env` file rather than committed to the compose file.

### `.env.example`

```
POSTGRES_USER=fintech_admin
POSTGRES_PASSWORD=change_me_locally
POSTGRES_DB=fintech_ledger

# FIXED (v1.3): RS256 is asymmetric -- a single shared JWT_SECRET (the v1.2
# draft here) is meaningless for it and directly contradicted §8.2's own
# RS256 mandate. Generate a real keypair (see §7's Secrets Manager note for
# where the private key lives in production) and point at both files.
JWT_PRIVATE_KEY_PATH=/app/keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/app/keys/jwt_public.pem
JWT_ALGORITHM=RS256
```

### `docker-compose.dev.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: fintech_postgres_dev
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: fintech_redis_dev
    ports:
      - "6379:6379"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: fintech_fastapi_dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      FRONTEND_URL: http://localhost:3000
      JWT_PRIVATE_KEY_PATH: ${JWT_PRIVATE_KEY_PATH}
      JWT_PUBLIC_KEY_PATH: ${JWT_PUBLIC_KEY_PATH}
      JWT_ALGORITHM: ${JWT_ALGORITHM}
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: fintech_next16_dev
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      WATCHPACK_POLLING: "true"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      - backend

volumes:
  postgres_dev_data:

```

*(The top-level `version:` key from the original file has been dropped — modern Docker Compose ignores it and recent versions warn on it.)*

### Execution Commands

```bash
# Start local environment with hot reloading
docker compose -f docker-compose.dev.yml up --build

# Access Services
# Frontend: http://localhost:3000
# FastAPI Swagger Docs: http://localhost:8000/docs

```

---

## 7. Zero-Cost GCP Cloud Deployment Strategy

The system is configured to run on Google Cloud Platform's permanent **Always-Free Tier**. This revises the original topology in two ways: Next.js 16 now deploys to **Firebase App Hosting** rather than classic Firebase Hosting (Google has closed new sign-ups to the old Hosting "frameworks experiment" that classic Hosting relied on for SSR, and now directs server-rendered Next.js apps to App Hosting instead, which runs on Cloud Build/Cloud Run under the hood), and Redis now has an explicit home, since GCP's own Memorystore isn't part of the Always-Free tier.

```
                         GCP ALWAYS-FREE TIER TOPOLOGY (REVISED)

 ┌─────────────────────────┐   ┌────────────────────────┐   ┌───────────────────────┐
 │  Firebase App Hosting    │   │      GCP Cloud Run      │   │  Supabase / Neon DB    │
 │  (Next.js 16, SSR)       │──>│   (FastAPI Container)   │──>│  (Free PostgreSQL)     │
 │  Runs on Cloud Run/Build │   │  Free: 2M requests/mo,  │   │  Free: 500 MB storage  │
 │  under the hood          │   │  360K vCPU-sec/mo       │   │                        │
 └─────────────────────────┘   └────────────┬─────────────┘   └───────────────────────┘
                                             │
                                             ▼
                                  ┌────────────────────────┐
                                  │      Upstash Redis      │
                                  │  Serverless free tier — │
                                  │  GCP Memorystore is NOT │
                                  │  part of Always-Free    │
                                  └────────────────────────┘
```

1. **Provision Free Serverless PostgreSQL:** 5 mins.
Create a free PostgreSQL instance on **Supabase** or **Neon.tech**. Retrieve your connection string (`postgresql+asyncpg://...`).

2. **Provision Free Redis:** 5 mins.
Create a free Upstash Redis database and retrieve its REST/TCP connection URL. Skip GCP Memorystore for this deployment — it bills per hour and isn't part of the Always-Free tier, which would break the "zero-cost" goal.

3. **Deploy FastAPI to Cloud Run:** 5 mins.
Authenticate the gcloud CLI, build the container image in Artifact Registry, and deploy to Cloud Run:
`gcloud run deploy fintech-api --image gcr.io/[PROJECT_ID]/fastapi-backend --platform managed --allow-unauthenticated`

4. **Deploy Next.js 16 to Firebase App Hosting:** 5–10 mins.
Run `firebase init apphosting`, connect the GitHub repo, and set `NEXT_PUBLIC_API_URL` to the live Cloud Run endpoint as a build-time environment variable. App Hosting builds and redeploys automatically on push, and supports SSR/App Router out of the box — unlike classic Firebase Hosting's static export.

5. **Same-origin routing for the auth cookie, and secrets (NEW, v1.3):** 10–15 mins.
Firebase App Hosting and Cloud Run sit on different Google-managed domains by default (`*.web.app`/a custom domain vs. `*.run.app`) — not same-site, which is a real problem given §8.2's refresh token is meant to be an HttpOnly, `SameSite=Strict` cookie. Add a Firebase Hosting rewrite so the backend is served from the *same* origin as the frontend:
   ```json
   // firebase.json
   {
     "hosting": {
       "rewrites": [
         { "source": "/api/**", "destination": "https://fintech-api-<hash>-<region>.a.run.app/**" }
       ]
     }
   }
   ```
   With `NEXT_PUBLIC_API_URL` pointed at `/api` instead of the raw Cloud Run URL, the browser only ever talks to one origin, and the cookie design in §8.2 works as specified in production — no separate load balancer needed. Local dev keeps the bearer-token fallback documented in §8.2, since faking same-origin across `localhost:3000`/`:8001` isn't worth the setup cost for a dev loop.

   Separately: store the RS256 private key in **GCP Secret Manager**, not baked into the container image or left as a bare file on disk. Cloud Run has native Secret Manager integration (mount as a volume or inject as an env var at deploy time), which matters specifically because Cloud Run is stateless and scales to zero — there's no persistent disk to keep a generated keypair on across cold starts or multiple instances. `gcloud run deploy` accepts `--set-secrets=/app/keys/jwt_private.pem=jwt-private-key:latest` to wire this up.

**Two free-tier limits worth planning around:** Cloud Run's Always-Free egress allowance is roughly 1 GiB/month — a receipt-heavy POS flow or an image-heavy underwriter dashboard can exceed that quickly, after which egress is billed per GB. And because Cloud Run scales to zero by default, the first request after an idle period pays a cold-start cost that includes loading the `joblib` model file — fine for a pilot, but worth monitoring once MFI partners have latency expectations. (Re-verify these figures against the provider's current published limits at deploy time — free-tier allowances change periodically.)

### 7.1 Ledger Capacity Planning on the Free-Tier Database (NEW, v1.2)

The `duka_transactions`, `chama_contributions`, and `loan_repayments` tables are append-only by design (§4) — rows are never deleted, only ever added. On a 500 MB free-tier Postgres instance, that's a running-out-of-room problem on a knowable timeline, not an if.

**Rough sizing:** a `duka_transactions` row (fixed columns + two 64-char hash strings + index overhead) lands in the neighborhood of 250–350 bytes on disk including index storage. At, say, 50 active merchants each logging 20 transactions/day, that's roughly 1,000 rows/day (~300KB/day, ~9MB/month) from the ledger table alone — before `chama_contributions`, `inventory_movements`, `loan_repayments`, and index growth on top of that. At this illustrative volume the 500MB ceiling is years away; at 10x the merchant count or transaction frequency, it's a matter of months. **Action item:** before onboarding real merchants, re-run this estimate against actual pilot volume (not the illustrative numbers above) to get a real runway figure.

**When it does approach the ceiling, options in order of preference:**
1. **Upgrade the DB tier** (Supabase Pro / Neon paid) once volume justifies it — the simplest fix, and the first free-tier limit that's likely to force a paid upgrade regardless of anything else in this document.
2. **Partition by time** (e.g. monthly partitions on `duka_transactions`) so older partitions can be moved to cheaper cold storage (e.g. a GCS export) without breaking the hash chain, which only requires the *previous* row in the same merchant's sequence to remain queryable, not the entire history.
3. **Archive, don't delete:** because of the `ON DELETE RESTRICT` / append-only design, "archiving" here means exporting old partitions to object storage for compliance retention, not deleting rows from the live table — deleting ledger rows would break both the audit trail and the immutability guarantee this whole schema exists to provide.

This is a design constraint worth surfacing to stakeholders early, since it affects the "Always-Free Tier" pitch: the free tier is free for a pilot's lifetime, not indefinitely at scale.

---

## 8. Security & Data Compliance Framework

1. **Data Protection & PII Privacy:** Underwriters query the anonymized `underwriter_applicant_view` (§4) rather than base tables directly — applicant name and phone number stay `NULL` until a loan's status moves to `APPROVED`. Borrower deletion requests under Kenya's Data Protection Act, 2019 are handled by soft-deleting `users` (`deleted_at`) and redacting PII fields, never by hard-deleting rows that ledger or loan records depend on for integrity. See §4's note on how loan creation resolves a borrower from `credit_score_id` without ever exposing a raw `user_id` to the underwriter (NEW, v1.3) — this anonymization guarantee extends through to the one write path that could otherwise have leaked identity.

2. **Phone/OTP Authentication:** Given `phone_number` is the primary identifier, login is realistically OTP-based (SMS/WhatsApp) rather than a full OAuth2 delegated-authorization flow — "OAuth2" in the original draft is more accurately described as "issue JWTs after OTP verification," unless a third-party identity provider is added later. JWTs use **RS256** rather than leaving HS256 as an open option: the private signing key stays on the backend, while the public key can be safely shared with the Underwriter Portal or MFI partner systems so they can verify tokens independently without ever handling the signing secret. Access tokens: 15-minute expiry. Refresh tokens: `HttpOnly`, `SameSite=Strict` cookies, tracked in `refresh_tokens` so any single session can be revoked, paired with CSRF protection (double-submit token) on state-changing requests that rely on the cookie.

   **Making the cookie design actually work in production (NEW, v1.3):** an HttpOnly/`SameSite=Strict` cookie only works same-site, and §7's own deployment topology puts the frontend (Firebase App Hosting) and backend (Cloud Run) on different Google-managed domains by default — not same-site out of the box. §7 step 5 now adds a Firebase Hosting rewrite (`/api/**` → the Cloud Run service) specifically so this cookie design is actually deliverable as specified, rather than silently falling back to a weaker scheme in production. Local dev still uses a bearer-token fallback (access + refresh tokens returned in the response body, held client-side) since faking same-origin across `localhost:3000`/`:8001` isn't worth the setup cost for a dev loop — that fallback is a deliberate, documented dev-only exception, not the production design.

   **OTP abuse protection (NEW, v1.2):** OTP-based login on a phone-number-primary system is a known target for SIM-swap fraud and OTP-flooding, both common in East African mobile-money-adjacent fintech. Backed by the new `otp_challenges` table:
   - Rate-limit OTP *requests* per phone number (e.g. max 3 per 15 minutes, with exponential backoff on repeated requests) to blunt flooding/DoS against a target's phone.
   - Cap OTP *verification attempts* per challenge (`max_attempts`, default 5) — lock the challenge after that, rather than allowing unlimited guesses against a 4–6 digit code.
   - On a successful login from a phone number that recently changed carriers or had a suspicious pattern of failed attempts, consider a secondary check (e.g. a cooldown period or manual review) before treating the session as fully trusted — a full SIM-swap detection pipeline is out of scope for the MVP, but the schema and rate limits above are the minimum viable defense.

   **Refresh token rotation (NEW, v1.2):** refresh tokens are single-use, not reused until natural expiry. Each successful `/refresh` call issues a new refresh token, sets `replaced_by` on the old row, and revokes the old token. If a token with a non-null `replaced_by` is ever presented again, treat it as a stolen/replayed token: revoke the entire token family (all descendants of that token for that user) and force re-authentication. This is what makes token theft detectable rather than just theoretically preventable.

3. **Immutability Auditing:** Enforced at three layers (v1.2 adds the first): a `BEFORE INSERT` trigger validates that each new ledger row's `previous_hash` correctly chains to the prior row, catching a broken or forged chain at write time; a `BEFORE UPDATE OR DELETE` trigger on `duka_transactions` rejects direct row mutation outright; and the application's database role is granted `INSERT, SELECT` only on ledger tables — no `UPDATE`/`DELETE` grant exists for any application-facing role. The SHA-256 hash chain remains additionally useful as an *external* verification mechanism for an auditor or MFI partner without direct database access.

4. **Licensing & Regulatory Posture:**
   - **CBK:** Since 2022, the Central Bank of Kenya (Digital Credit Providers) Regulations require anyone carrying out digital credit business to hold a CBK license, unless already regulated under another law (e.g. as a bank, microfinance institution, or Sacco society). If this platform only scores applicants and hands lending decisions to already-licensed MFI partners, it likely sits outside that licensing scope — but the `loans`/`loan_repayments` tables imply the platform may originate or disburse credit directly, which would put it inside scope. Confirm the intended lending model with legal counsel before the Underwriter Portal goes live with real money.
   - **ODPC (NEW, v1.2):** Separately from CBK licensing, this platform processes personal data (phone numbers, transaction history, and — if the gap noted in §5.2 is closed — sensitive category data like gender) at a scale that likely requires registration as a data controller/processor with Kenya's Office of the Data Protection Commissioner under the Data Protection Act, 2019, regardless of the CBK licensing outcome. Confirm registration status and any applicable Data Protection Impact Assessment (DPIA) requirement alongside the CBK question, before launch.

5. **Write Reliability: Idempotency, Pagination, and Concurrency (NEW, v1.3):**
   - **Idempotency-Key on money-handling writes:** `POST /ledger/transactions/{sale,expense,supplier-payment}` accept an optional `Idempotency-Key` header. The first successful call's response is stored in `idempotency_keys` keyed on `(user_id, idempotency_key, endpoint)`; a retried request with the same key returns the original response instead of re-running the write. This specifically protects against the flaky-mobile-connection case — a client that times out waiting for a response and retries must not create a second real ledger entry. No key supplied means no deduplication, matching how most HTTP clients that haven't opted in behave today. Two truly simultaneous requests with the same key can still both attempt the write; the `UNIQUE` constraint lets only one commit, and the loser's entire transaction (including its ledger write) rolls back rather than partially applying — the client sees an error and a retry converges to the single correct result. That residual case is rare enough (it requires millisecond-level concurrent duplicate submission, not just a sequential retry) not to warrant finer-grained locking unless observed in practice.
   - **Pagination:** see §4's pagination note — every list endpoint now takes `limit`/`offset` (default 50, max 200) and returns `{items, total, limit, offset}`.
   - **Concurrency on ledger `sequence_no`:** see §4's concurrency note — a Postgres advisory lock keyed on `merchant_id` is the recommended fix for the sequence-allocation race, tracked but not yet implemented.

6. **Role Provisioning & Admin Management (NEW, v1.4):**
   - **Self-registration is restricted to `MERCHANT`/`CHAMA_MEMBER`.** The public OTP signup flow rejects an attempt to self-assign `UNDERWRITER` or `ADMIN` (403) — those roles carry access to the applicant view and loan approval, and letting anyone self-select into them at signup was a straightforward privilege-escalation path, not a legitimate onboarding flow.
   - **`UNDERWRITER`/`ADMIN` accounts are created exclusively by an existing admin**, via `POST /admin/users` (gated by `require_role("ADMIN")` at the router level, applied to the whole `/admin/*` prefix). The created account then logs in through the ordinary, unmodified OTP flow — since the phone number already has a role assigned, no role picker is ever shown and no invite/redemption step exists to build or secure.
   - **The very first admin is bootstrapped out-of-band**, via `scripts/create_admin.py` run directly against the database by whoever operates the deployment — the same pattern as `scripts/generate_jwt_keys.py`. This is the one deliberate exception to "everything goes through the API": there is no admin yet to call `POST /admin/users` for the first one.
   - **Admin actions available:** create a user (any role), list/filter users by role and active status (paginated), update a user's name or role, deactivate an account, reactivate it. There is no "reset password" action — this is OTP-only auth with no password to reset; deactivation (which also revokes all of that user's outstanding refresh tokens immediately) is the equivalent for "lock this account out now."
   - **Every admin-created account records who created it** via `users.created_by`, giving a minimal audit trail for who onboarded a given underwriter or admin, without a separate audit-log table.
   - **Deactivation actually blocks login** (a correctness fix that shipped alongside this feature): the OTP verify flow now checks for a deactivated *existing* account before falling through to the "not registered" branch, so a deactivated user can't be silently re-registered with a fresh name/role the next time they attempt to log in.

7. **Anti-Gaming Controls on Scoring Inputs (NEW, v1.5):** the hash chain in §4 guarantees a ledger row can't be edited or deleted after the fact — it does not guarantee the row was ever real. These controls address that separate, more important problem for the sales/inventory and chama-punctuality inputs specifically:
   - `POST /ledger/transactions/sale` requires at least one line item, rejecting revenue that isn't tied to any inventory movement (422 if omitted).
   - Every line item's `product_id` (and every `POST /ledger/products/{id}/restock` target) must belong to the acting merchant (403 otherwise) — previously neither check existed, so a merchant could reference or restock another merchant's inventory.
   - `POST /chama/contributions` requires the acting user to be a `CHAIRPERSON`/`TREASURER`/`SECRETARY` of that specific chama, and forbids recording a contribution for themselves — a plain member (or the member being credited) attesting to their own punctuality no longer works.
   - `margin_stability` is windowed to the same rolling 30 days as `sales_velocity`, so a single fabricated burst decays instead of permanently distorting the feature.
   - **Not addressed by any of the above:** the data is still entirely self-reported (no external payment-rail corroboration), the merchant still controls the timing of their own score evaluation, the `receivables_days` proxy (§5.1) remains gameable via a fabricated `customer_phone`, and there's no statistical anomaly detection surfaced to the underwriter. See the v1.5 revision notes at the top of this document for the full reasoning.
