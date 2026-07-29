import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.modules.chama.domain.repository import ChamaContributionRepository, ChamaMemberRepository
from app.modules.ledger.domain.repository import LedgerRepository, ProductRepository
from app.modules.scoring.application.exceptions import LoanNotFound
from app.modules.scoring.domain.entities import ApplicantView, CreditScore, Loan, LoanRepayment
from app.modules.scoring.domain.repository import CreditScoreRepository, LoanRepository
from app.modules.scoring.infrastructure.scoring_engine import AlternativeCreditScorer, MerchantFeatures

FEATURE_WINDOW_DAYS = 30

# Anomaly-flag heuristic thresholds (platform-cross-cutting spec §3.4d) --
# a cheap triage signal, not a fraud model. Tuned to be conservative (few
# false positives) rather than sensitive, since a wrongly-flagged merchant
# has no way to contest it.
ANOMALY_VOLUME_SPIKE_WINDOW_DAYS = 3
ANOMALY_VOLUME_SPIKE_RATIO = 0.8
ANOMALY_MARGIN_MIN_DAYS = 3
ANOMALY_MARGIN_VARIANCE_THRESHOLD = 0.0005


class ComputeMerchantFeatures:
    """Cross-context read: aggregates ledger + chama data into the feature
    vector the scoring engine expects. Lives in scoring's application layer
    (not ledger's or chama's) since it's scoring's concern how those two
    contexts' data gets combined -- ledger and chama don't know this
    consumer exists."""

    def __init__(
        self,
        ledger_repo: LedgerRepository,
        product_repo: ProductRepository,
        member_repo: ChamaMemberRepository,
        contribution_repo: ChamaContributionRepository,
    ):
        self.ledger_repo = ledger_repo
        self.product_repo = product_repo
        self.member_repo = member_repo
        self.contribution_repo = contribution_repo

    async def execute(self, user_id: str) -> MerchantFeatures:
        since = datetime.now(timezone.utc) - timedelta(days=FEATURE_WINDOW_DAYS)

        revenue_30d = await self.ledger_repo.sales_total_since(user_id, since)
        active_days = await self.ledger_repo.active_business_days_since(user_id, since)
        sales_velocity = float(revenue_30d) / active_days if active_days > 0 else 0.0

        receivables_days = await self.ledger_repo.avg_receivables_days(user_id)
        margin_stability = await self.product_repo.margin_stability(user_id, since)

        memberships = await self.member_repo.list_for_user(user_id)
        if memberships:
            scores = [await self.contribution_repo.punctuality(m.id) for m in memberships]
            chama_punctuality = sum(scores) / len(scores)
        else:
            chama_punctuality = 0.0

        return MerchantFeatures(
            sales_velocity=sales_velocity,
            receivables_days=receivables_days,
            chama_punctuality=chama_punctuality,
            margin_stability=margin_stability,
        )


class DetectAnomalyFlags:
    """Cheap heuristic triage signals computed alongside a score (platform
    cross-cutting spec §3.4d) -- explicitly NOT a fraud model. Each flag is
    a "worth a second look" signal, not a guarantee; frame it to
    stakeholders the same way. Independent of ComputeMerchantFeatures on
    purpose: these thresholds are tuned for anomaly triage, not for the
    scoring model's feature scale, so reusing its aggregates would
    conflate two different concerns."""

    def __init__(self, ledger_repo: LedgerRepository, product_repo: ProductRepository):
        self.ledger_repo = ledger_repo
        self.product_repo = product_repo

    async def execute(self, user_id: str) -> list[str]:
        flags: list[str] = []
        now = datetime.now(timezone.utc)

        revenue_30d = await self.ledger_repo.sales_total_since(user_id, now - timedelta(days=FEATURE_WINDOW_DAYS))
        revenue_recent = await self.ledger_repo.sales_total_since(user_id, now - timedelta(days=ANOMALY_VOLUME_SPIKE_WINDOW_DAYS))
        if revenue_30d > 0 and (revenue_recent / revenue_30d) > Decimal(str(ANOMALY_VOLUME_SPIKE_RATIO)):
            flags.append("VOLUME_SPIKE_LAST_3_DAYS")

        daily_ratios = await self.product_repo.daily_margin_ratios(user_id, now - timedelta(days=FEATURE_WINDOW_DAYS))
        if len(daily_ratios) >= ANOMALY_MARGIN_MIN_DAYS and statistics.pvariance(daily_ratios) < ANOMALY_MARGIN_VARIANCE_THRESHOLD:
            flags.append("IMPLAUSIBLY_SMOOTH_MARGIN")

        return flags


class EvaluateMerchant:
    def __init__(
        self,
        compute_features: ComputeMerchantFeatures,
        engine: AlternativeCreditScorer,
        score_repo: CreditScoreRepository,
        detect_anomalies: DetectAnomalyFlags,
    ):
        self.compute_features = compute_features
        self.engine = engine
        self.score_repo = score_repo
        self.detect_anomalies = detect_anomalies

    async def execute(self, user_id: str) -> CreditScore:
        features = await self.compute_features.execute(user_id)
        credit_score, risk_tier, shap_dict = await self.engine.evaluate_merchant(user_id, features)
        anomaly_flags = await self.detect_anomalies.execute(user_id)

        # Recommended limit: a conservative multiple of 30-day sales velocity,
        # scaled down for higher-risk tiers. Placeholder policy pending a real
        # underwriting-limit model -- see the PDO-scaling note in scoring_engine.py.
        tier_multiplier = {"LOW": 3.0, "MEDIUM": 1.5, "HIGH": 0.5}[risk_tier]
        recommended_limit = Decimal(str(round(features.sales_velocity * 30 * tier_multiplier, 2)))

        return await self.score_repo.save(
            user_id=user_id,
            credit_score=credit_score,
            recommended_limit=recommended_limit,
            risk_tier=risk_tier,
            model_version=self.engine.model_version,
            shap_explanation=shap_dict,
            anomaly_flags=anomaly_flags,
        )


class CreateLoan:
    def __init__(self, loan_repo: LoanRepository, score_repo: CreditScoreRepository):
        self.loan_repo = loan_repo
        self.score_repo = score_repo

    async def execute(
        self,
        *,
        borrower_id: str,
        underwriting_method: str,
        principal: Decimal,
        interest_rate: Decimal,
        credit_score_id: str | None = None,
        override_reason: str | None = None,
        due_date: date | None = None,
    ) -> Loan:
        if underwriting_method == "ALGORITHMIC" and credit_score_id is None:
            raise ValueError("ALGORITHMIC loans require a credit_score_id")
        if underwriting_method != "ALGORITHMIC" and not override_reason:
            raise ValueError("MANUAL/OVERRIDE loans require an override_reason")
        if credit_score_id is not None and await self.score_repo.get(credit_score_id) is None:
            raise ValueError("credit_score_id does not exist")

        return await self.loan_repo.create(
            borrower_id=borrower_id,
            credit_score_id=credit_score_id,
            underwriting_method=underwriting_method,
            override_reason=override_reason,
            principal=principal,
            interest_rate=interest_rate,
            due_date=due_date,
        )


class RecordRepayment:
    def __init__(self, loan_repo: LoanRepository):
        self.loan_repo = loan_repo

    async def execute(self, loan_id: str, amount: Decimal) -> LoanRepayment:
        return await self.loan_repo.record_repayment(loan_id, amount)


class ListApplicants:
    def __init__(self, loan_repo: LoanRepository):
        self.loan_repo = loan_repo

    async def execute(self, limit: int, offset: int) -> tuple[list[ApplicantView], int]:
        return await self.loan_repo.list_applicants(limit, offset)


class ListLoanRepayments:
    """Fetches the loan alongside its repayments (rather than just the
    repayments) so the router can enforce the "own loan or UNDERWRITER"
    ownership check without a second round-trip -- mirrors the ownership
    check already done inline for /scoring/scores/{user_id}/latest."""

    def __init__(self, loan_repo: LoanRepository):
        self.loan_repo = loan_repo

    async def execute(self, loan_id: str, *, limit: int, offset: int) -> tuple[Loan, list[LoanRepayment], int]:
        loan = await self.loan_repo.get(loan_id)
        if loan is None:
            raise LoanNotFound(loan_id)
        repayments, total = await self.loan_repo.list_repayments_for_loan(loan_id, limit, offset)
        return loan, repayments, total
