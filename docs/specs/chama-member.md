# CHAMA_MEMBER Journey — Implementation Spec

**Companion to:** [`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md) (v1.5), [`USER_JOURNEYS.md`](../USER_JOURNEYS.md) §2

**Audience:** an engineering agent picking up remaining CHAMA_MEMBER-journey work with no prior session context.

---

## 1. Role & Purpose

A `CHAMA_MEMBER` participates in savings circles (chamas) with no shop of their own (a `MERCHANT` can also do everything in this journey — see `USER_JOURNEYS.md` §1.4). Self-registers via OTP like `MERCHANT`.

## 2. Current Implementation (do not rebuild this)

**Backend**, `backend/app/modules/chama/` (domain/application/infrastructure/presentation):
- `POST /chama/groups` — create a chama; creator becomes `CHAIRPERSON`.
- `GET /chama/groups` — paginated, chamas the caller belongs to.
- `POST /chama/groups/{chama_id}/members` — add a member by `user_id` + role.
- `GET /chama/groups/{chama_id}/members` — paginated.
- `POST /chama/contributions` — **duty-separated as of v1.5**: rejects if the acting user is the member being credited, or isn't a `CHAIRPERSON`/`TREASURER`/`SECRETARY` of that chama (403 either way). See `app/modules/chama/application/exceptions.py` (`CannotRecordOwnContribution`, `NotAuthorizedToRecordContribution`) and `RecordContribution` in `application/use_cases.py`.
- `GET /chama/members/{member_id}/punctuality` — on-time % for a member.
- `POST /chama/payouts` — schedule a merry-go-round payout (exists, unused by frontend).

**Backend, exists but not exposed via any endpoint** (repository methods only):
- `ChamaContributionRepository.list_for_member(member_id)` — full contribution history for one member.
- `ChamaPayoutRepository.list_for_chama(chama_id)` — scheduled payouts for a chama.

**Frontend**, `frontend/src/features/chama-portal/`, rendered on `app/(dashboard)/chama/page.tsx`:
- `ChamaList.tsx` — list + create chama.
- `ChamaDetail.tsx` — add member, member table with punctuality, record-contribution mini-form. Surfaces the v1.5 duty-separation 403 as a clear inline message (see `contributionError` state in the component) rather than a silent failure.

## 3. Conventions to Follow

Same as the merchant spec §3 — DDD layering, `Page[T]` pagination, module-specific `application/exceptions.py`, React Query hooks unwrapping `Page<T>.items`.

One chama-specific convention: **duty separation is enforced in the application layer** (`RecordContribution.execute`), not the router — any new write that should respect "who can attest to what" needs to look up the acting user's `ChamaMember` row via `member_repo.get_for_user(chama_id, acting_user_id)` and check `member_role` the same way, rather than re-implementing an ad hoc check in the router.

## 4. Work Items

### 4.1 Contribution history endpoint + UI

**Goal:** a member (or an officer, on their behalf) can see a member's full contribution history — not just the current punctuality percentage.

**Why:** `ChamaContributionRepository.list_for_member` already exists and works; there's no `GET` endpoint exposing it and no frontend view.

**Proposed design:**
- Add `GET /chama/members/{member_id}/contributions` to `chama/presentation/router.py`, paginated (`Page[ContributionOut]`) — mirror the pagination pattern already used by `GET /chama/groups/{chama_id}/members`. Update `ChamaContributionRepository.list_for_member` to accept `limit`/`offset` and return `(items, total)` (currently returns a bare list — this needs the same signature change `list_for_chama` on `ChamaMemberRepository` already went through for pagination).
- Frontend: new `useContributions(memberId, {limit, offset})` hook in `features/chama-portal/api/index.ts`; a `ContributionHistoryTable.tsx` component, shown when a member row is selected in `ChamaDetail.tsx` (reuse the existing `selectedMemberId` state — add a second panel below the "record contribution" form, not a replacement for it).
- Who can view: any member of that chama (not just officers — viewing your own or others' contribution history isn't the sensitive action, *recording* one is). Verify the caller has a `ChamaMember` row for this `chama_id` before returning data; 403 otherwise.

**Acceptance criteria:**
- Returns `is_on_time`, `amount_due`, `amount_paid`, `cycle_due_date`, `paid_at`, paginated, newest-cycle-first (matches existing `idx_chama_contrib_member` index ordering: `member_id, cycle_due_date DESC`).
- A user with no membership in the chama gets 403, not an empty list (don't leak whether the chama/member exists).

**Files likely touched:** `chama/domain/repository.py`, `chama/infrastructure/repository.py`, `chama/application/use_cases.py` (new `ListContributions` use case, mirroring `ListMembers`), `chama/presentation/{router,schemas}.py`, `frontend/src/features/chama-portal/{api,components}/`.

---

### 4.2 Payout schedule endpoint + UI

**Goal:** members can see the merry-go-round payout schedule for their chama — who's due to receive a payout and when.

**Why:** `POST /chama/payouts` exists (an officer can schedule one) but there's no way to *view* the schedule — `ChamaPayoutRepository.list_for_chama` is implemented and unused.

**Proposed design:**
- Add `GET /chama/groups/{chama_id}/payouts` to `chama/presentation/router.py`, paginated. Update `ChamaPayoutRepository.list_for_chama` to accept `limit`/`offset` (same signature-change pattern as 4.1).
- Frontend: `usePayouts(chamaId)` hook + a `PayoutScheduleTable.tsx`, shown as a new tab/section on the chama detail view (recipient member, amount, scheduled date, paid-out date or "pending").
- Access: any member of the chama can view (same reasoning as 4.1 — viewing isn't the sensitive action).
- Consider whether `POST /chama/payouts` should also gain an officer-only check while this is being touched — **it currently has none at all** (any authenticated user can schedule a payout for any chama). This is arguably a bigger gap than the missing view and worth fixing in the same pass; if you do, follow the exact `OFFICER_ROLES` check pattern from `RecordContribution`.

**Acceptance criteria:**
- Schedule is paginated, ordered by `scheduled_date`.
- (If bundled) scheduling a payout is rejected for a non-officer, matching the contribution-recording precedent.

**Files likely touched:** `chama/domain/repository.py`, `chama/infrastructure/repository.py`, `chama/application/use_cases.py`, `chama/presentation/{router,schemas}.py`, `frontend/src/features/chama-portal/`.

---

## 5. Out of Scope for This Spec

- Adding a member self-service "leave chama" or officer-transfer flow — not currently requested, would need real product design (what happens to their contribution history, who becomes chairperson).
- Anti-gaming hardening beyond the v1.5 duty-separation fix — tracked in the platform cross-cutting spec.
