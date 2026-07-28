from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.modules.identity.application.exceptions import (
    OtpInvalid,
    OtpLocked,
    OtpRateLimited,
    RefreshTokenInvalid,
    RefreshTokenReused,
    UserNotRegistered,
)
from app.modules.identity.application.use_cases import Logout, RefreshTokenRotation, RequestOtp, VerifyOtp
from app.modules.identity.domain.entities import InvalidPhoneNumber
from app.modules.identity.infrastructure.otp_sender import ConsoleOtpSender
from app.modules.identity.infrastructure.repository import (
    SqlOtpChallengeRepository,
    SqlRefreshTokenRepository,
    SqlUserRepository,
)
from app.modules.identity.presentation.schemas import (
    AccessTokenOut,
    LogoutIn,
    OtpRequestIn,
    OtpVerifyIn,
    RefreshIn,
    TokenPairOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_otp(
    body: OtpRequestIn, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> None:
    use_case = RequestOtp(SqlOtpChallengeRepository(db), ConsoleOtpSender(), settings)
    try:
        await use_case.execute(body.phone_number)
        await db.commit()
    except InvalidPhoneNumber as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except OtpRateLimited as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc


@router.post("/otp/verify", response_model=TokenPairOut)
async def verify_otp(
    body: OtpVerifyIn, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> TokenPairOut:
    use_case = VerifyOtp(SqlOtpChallengeRepository(db), SqlUserRepository(db), SqlRefreshTokenRepository(db), settings)
    try:
        access_token, refresh_token, user = await use_case.execute(
            body.phone_number, body.code, full_name=body.full_name, role=body.role
        )
        await db.commit()
    except InvalidPhoneNumber as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (OtpInvalid, OtpLocked) as exc:
        await db.commit()  # persist the incremented attempt count even on failure
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except UserNotRegistered as exc:
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return TokenPairOut(access_token=access_token, refresh_token=refresh_token, user_id=user.id, role=user.role)


@router.post("/refresh", response_model=AccessTokenOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> AccessTokenOut:
    use_case = RefreshTokenRotation(SqlRefreshTokenRepository(db), SqlUserRepository(db), settings)
    try:
        access_token, refresh_token = await use_case.execute(body.refresh_token)
        await db.commit()
    except RefreshTokenReused as exc:
        await db.commit()  # persist the family revocation even though we're rejecting this request
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except RefreshTokenInvalid as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    return AccessTokenOut(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutIn, db: AsyncSession = Depends(get_db)) -> None:
    await Logout(SqlRefreshTokenRepository(db)).execute(body.refresh_token)
    await db.commit()
