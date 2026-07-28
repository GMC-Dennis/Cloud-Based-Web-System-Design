from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://fintech_admin:change_me_locally@localhost:5432/fintech_ledger"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:3000"

    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    otp_length: int = 6
    otp_expire_minutes: int = 5
    otp_max_attempts: int = 5
    otp_max_requests_per_window: int = 3
    otp_request_window_minutes: int = 15
    otp_pepper: str = "change_me_locally"

    model_version: str = "rf_v3_2026_06"


@lru_cache
def get_settings() -> Settings:
    return Settings()
