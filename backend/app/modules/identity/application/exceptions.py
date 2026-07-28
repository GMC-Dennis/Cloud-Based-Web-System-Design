class OtpRateLimited(Exception):
    pass


class OtpInvalid(Exception):
    pass


class OtpLocked(Exception):
    pass


class UserNotRegistered(Exception):
    pass


class RoleNotSelfAssignable(Exception):
    """Raised when a brand-new phone number's first login attempts to
    self-register as UNDERWRITER or ADMIN. Those roles must be provisioned
    by an existing admin (see identity/application/admin_use_cases.py) --
    self-selecting into them at public signup is a privilege-escalation gap,
    not a legitimate onboarding path."""

    pass


class AccountDeactivated(Exception):
    """Raised when a *registered* phone number has been deactivated by an
    admin. Distinct from UserNotRegistered: a deactivated user must not be
    silently treated as brand-new and re-prompted to sign up again."""

    pass


class RefreshTokenInvalid(Exception):
    pass


class RefreshTokenReused(Exception):
    """Raised when a refresh token that was already rotated (has a non-null
    replaced_by) is presented again -- signals likely token theft."""

    pass
