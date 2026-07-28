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
