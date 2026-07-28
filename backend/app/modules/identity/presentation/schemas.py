from pydantic import BaseModel, Field


class OtpRequestIn(BaseModel):
    phone_number: str = Field(examples=["+254712345678"])


class OtpVerifyIn(BaseModel):
    phone_number: str
    code: str = Field(min_length=4, max_length=8)
    full_name: str | None = None
    role: str | None = Field(
        default=None,
        description="Required on first-time login: MERCHANT or CHAMA_MEMBER only. "
        "UNDERWRITER/ADMIN accounts must be provisioned by an existing admin, not self-assigned here.",
    )


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class RefreshIn(BaseModel):
    refresh_token: str


class AccessTokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutIn(BaseModel):
    refresh_token: str
