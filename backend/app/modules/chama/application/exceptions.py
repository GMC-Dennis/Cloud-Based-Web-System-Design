class CannotRecordOwnContribution(Exception):
    """Real chama social accountability comes from an officer attesting to a
    member's payment, not the member attesting to their own. Without this
    check, a member could confirm their own contribution as on-time,
    fabricating the punctuality feature that feeds credit scoring."""

    pass


class NotAuthorizedToRecordContribution(Exception):
    """Only an officer (CHAIRPERSON/TREASURER/SECRETARY) of the *same* chama
    can record a contribution -- an unrelated authenticated user, or a plain
    MEMBER, cannot attest to someone else's payment either."""

    pass


class MemberNotFound(Exception):
    pass


class NotAMemberOfThisChama(Exception):
    """Viewing another member's contribution history, or a chama's payout
    schedule, isn't the sensitive action -- *recording* a contribution or
    *scheduling* a payout is (see CannotRecordOwnContribution /
    NotAuthorizedToRecordContribution above). But it's still chama-internal
    data: an unrelated authenticated user shouldn't be able to browse a
    chama they don't belong to."""

    pass


class NotAuthorizedToSchedulePayout(Exception):
    """Only an officer (CHAIRPERSON/TREASURER/SECRETARY) of this chama can
    schedule a payout. POST /chama/payouts previously had no check at all
    beyond "some valid login" -- this closes that gap with the same
    OFFICER_ROLES pattern RecordContribution already established."""

    pass
