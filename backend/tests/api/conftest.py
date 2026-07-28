import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
def sent_otps(monkeypatch):
    """Captures codes ConsoleOtpSender would have sent, keyed by phone number.

    More robust than scraping caplog for the logged line: log capture across
    pytest-asyncio's event-loop handling turned out to be unreliable here,
    and monkeypatching the sender directly is the more standard way to
    assert on an outbound side effect anyway.
    """
    from app.modules.identity.infrastructure.otp_sender import ConsoleOtpSender

    captured: dict[str, str] = {}

    async def fake_send(self, phone_number: str, code: str) -> None:
        captured[phone_number] = code

    monkeypatch.setattr(ConsoleOtpSender, "send", fake_send)
    return captured


@pytest_asyncio.fixture
async def client(db_session):
    # db_session already truncated the test DB for us; import app.main lazily
    # so it picks up the test DATABASE_URL/JWT key env vars conftest.py sets.
    from app.main import app

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


class LifespanManager:
    """Minimal lifespan context so the scoring model (or its absence) is
    handled the same way it would be under uvicorn, without pulling in a
    separate test dependency just for this."""

    def __init__(self, app):
        self.app = app

    async def __aenter__(self):
        self._ctx = self.app.router.lifespan_context(self.app)
        await self._ctx.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self._ctx.__aexit__(*exc)
