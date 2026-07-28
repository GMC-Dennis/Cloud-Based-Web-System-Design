# ADMIN Journey — Implementation Spec

**Companion to:** [`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md) (v1.5), [`USER_JOURNEYS.md`](../USER_JOURNEYS.md) §4

**Audience:** an engineering agent picking up remaining ADMIN-journey work with no prior session context.

---

## 1. Role & Purpose

An `ADMIN` operates the platform: onboards `UNDERWRITER`/`ADMIN` accounts (the only role that can), manages user accounts (edit, deactivate, reactivate). **Cannot self-register** — the very first admin is bootstrapped out-of-band via `scripts/create_admin.py`; every subsequent admin/underwriter is created by an existing admin through the app.

## 2. Current Implementation (do not rebuild this)

**Backend**, `backend/app/modules/identity/` — admin capability lives in the `identity` bounded context alongside auth (not a separate module), specifically `identity/application/admin_use_cases.py` and `identity/presentation/admin_router.py`:
- `POST /admin/users` — create a user with any role (this is the only path that can set `UNDERWRITER`/`ADMIN`). Rejects a duplicate phone number (409).
- `GET /admin/users` — paginated, filterable by `role` and `include_inactive`.
- `PATCH /admin/users/{user_id}` — update `full_name`/`role`.
- `POST /admin/users/{user_id}/deactivate` — soft-delete (`deleted_at`) + revokes all the user's refresh tokens immediately.
- `POST /admin/users/{user_id}/reactivate` — clears `deleted_at`.
- All of `/admin/*` is gated at the router level: `APIRouter(prefix="/admin", ..., dependencies=[Depends(require_role("ADMIN"))])`.
- `users.created_by` (nullable, self-referential FK) records who provisioned each account — the only audit trail that currently exists.
- `scripts/create_admin.py` — bootstraps the first admin; safe to re-run (detects an existing phone number and no-ops rather than erroring or duplicating).

**Frontend**, `frontend/src/features/admin/`, rendered on `app/(dashboard)/admin/page.tsx`:
- `CreateUserForm.tsx` — phone, name, role picker (all four roles selectable here, unlike the public signup picker).
- `UserTable.tsx` — paginated, filterable (role, include-deactivated toggle), inline edit, deactivate/reactivate row actions.

## 3. Conventions to Follow

Same as the merchant spec §3. Additionally:
- **Self-registration must never gain the ability to set `UNDERWRITER`/`ADMIN`.** `VerifyOtp` in `identity/application/use_cases.py` checks `role not in SELF_ASSIGNABLE_ROLES` (`app/modules/identity/domain/entities.py`) on the self-registration path. Any future change to signup must not weaken this — it's the fix for a real privilege-escalation gap (TDD v1.4 revision notes), not an arbitrary restriction.
- **Deactivation must stay "real."** `DeactivateUser` revokes all outstanding refresh tokens as part of deactivating, not as an afterthought — if you touch this use case, preserve that (a deactivated account that can still refresh its session defeats the point).
- **`get_by_phone` vs. `get_by_phone_any_status` / `get_by_id` vs. `get_by_id_any_status`**: the identity repository deliberately has both an active-only and an any-status lookup for users. Active-only (`get_by_phone`, `get_by_id`) is for request-time auth (a deactivated user's token must not resolve). Any-status (`get_by_phone_any_status`, `get_by_id_any_status`) is for admin actions, which need to see and act on deactivated accounts too (e.g. reactivating one). Using the wrong one is an easy, hard-to-notice bug — `ReactivateUser` looking up via the active-only method would never find the deactivated account it's supposed to reactivate.

## 4. Work Items

### 4.1 Admin action audit log

**Goal:** independently log who did what — role changes, deactivations, reactivations — with a timestamp and actor, beyond the single `users.created_by` field.

**Why:** right now, `created_by` tells you who *created* an account, but nothing records who deactivated a user last Tuesday, or who changed someone's role from `MERCHANT` to `UNDERWRITER` (which shouldn't even be possible via `PATCH /admin/users/{id}` today — see the open question below). For a platform that hands out loan-approval authority, this is a real gap for accountability, not a nice-to-have.

**Proposed design:**
- New table `admin_audit_log`: `id UUID PK, actor_user_id UUID NOT NULL REFERENCES users(id), target_user_id UUID REFERENCES users(id), action VARCHAR(30) NOT NULL CHECK (action IN ('CREATE_USER', 'UPDATE_USER', 'DEACTIVATE_USER', 'REACTIVATE_USER')), detail JSONB, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`. Append-only (no update/delete path needed — an audit log that can be edited isn't one; consider whether it needs the same trigger-enforced immutability pattern as `duka_transactions`, TDD §4, given the precedent already exists in this codebase).
- `detail` JSONB captures what changed (e.g. `{"before": {"role": "MERCHANT"}, "after": {"role": "UNDERWRITER"}}` for an update) — same idea as `credit_scores.shap_explanation`, structured but flexible.
- Write to this log from inside each existing admin use case (`CreateUserByAdmin`, `UpdateUser`, `DeactivateUser`, `ReactivateUser`) — inject a new `AuditLogRepository` alongside the existing repos, following the constructor-injection pattern already used throughout (e.g. `DeactivateUser.__init__(self, user_repo, refresh_repo)` becomes `..., audit_repo)`).
- New read endpoint `GET /admin/audit-log` (paginated, filterable by `target_user_id` and `action`), `ADMIN`-only.
- Frontend: a simple paginated table on `/admin`, perhaps a second tab/section below the user table — actor name, action, target, timestamp, expandable detail.

**Acceptance criteria:**
- Every one of the four admin actions produces exactly one audit row.
- The log is queryable per-user (both as actor and as target) for the pagination filters.
- No admin action succeeds if the audit write fails (same transaction — don't fire-and-forget it; if using the same `db: AsyncSession` and committing once at the end of the router handler, this falls out for free).

**Files likely touched:** new `alembic/versions/000X_admin_audit_log.py`, new `identity/infrastructure/models.py` addition (or a small dedicated model file, consistent with how `app/core/idempotency.py` keeps its own cross-cutting model separate from a bounded context — audit logging arguably belongs in `core/` rather than `identity/`, since conceivably other modules could want to write to it later; use your judgment but document the choice), `identity/domain/repository.py`, `identity/infrastructure/repository.py`, `identity/application/admin_use_cases.py`, `identity/presentation/admin_router.py`, frontend `features/admin/`.

**Open question to resolve before implementing:** should `PATCH /admin/users/{id}` continue to allow changing *any* role freely (including promoting a `MERCHANT` straight to `ADMIN`), or should role escalation specifically require a stricter path (e.g. only settable at creation, or requiring a second admin's confirmation)? The current implementation allows arbitrary role changes via `UpdateUser` with no additional check beyond "caller is an admin" — worth deciding if that's the intended trust model before you also start logging it as normal.

---

## 5. Out of Scope for This Spec

- Multi-admin approval workflows (e.g. requiring two admins to promote a third to `ADMIN`) — not requested, would need real product design.
- Self-service password/session reset — deliberately not built; this is OTP-only auth with no password, and deactivation already covers "lock this account out now" (TDD §8 item 6).
