class OtpRateLimited(Exception):
    pass


class OtpInvalid(Exception):
    pass


class OtpLocked(Exception):
    pass


class UserNotRegistered(Exception):
    pass


class RefreshTokenInvalid(Exception):
    pass


class RefreshTokenReused(Exception):
    """Raised when a refresh token that was already rotated (has a non-null
    replaced_by) is presented again -- signals likely token theft."""

    pass
