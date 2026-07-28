import logging
from typing import Protocol

logger = logging.getLogger("otp")


class OtpSender(Protocol):
    async def send(self, phone_number: str, code: str) -> None: ...


class ConsoleOtpSender:
    """Dev-mode implementation: logs the code instead of sending SMS/WhatsApp.
    Swap for a real Africa's Talking / Twilio-backed sender before any real
    deployment -- this is the only thing that needs to change."""

    async def send(self, phone_number: str, code: str) -> None:
        logger.info("OTP for %s: %s", phone_number, code)
