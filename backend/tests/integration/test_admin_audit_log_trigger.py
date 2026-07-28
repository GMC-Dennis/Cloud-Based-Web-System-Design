import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.audit_log import AdminAuditLogRecord, AuditLogRepository


async def _insert_and_get_id(db_session, test_user) -> str:
    await AuditLogRepository(db_session).record(actor_user_id=test_user.id, target_user_id=test_user.id, action="CREATE_USER")
    return (await db_session.execute(select(AdminAuditLogRecord))).scalar_one().id


async def test_insert_succeeds(db_session, test_user):
    await AuditLogRepository(db_session).record(
        actor_user_id=test_user.id, target_user_id=test_user.id, action="CREATE_USER", detail={"role": "MERCHANT"}
    )


async def test_update_is_rejected_by_append_only_trigger(db_session, test_user):
    row_id = await _insert_and_get_id(db_session, test_user)

    with pytest.raises((IntegrityError, DBAPIError)):
        await db_session.execute(update(AdminAuditLogRecord).where(AdminAuditLogRecord.id == row_id).values(action="UPDATE_USER"))
        await db_session.flush()


async def test_delete_is_rejected_by_append_only_trigger(db_session, test_user):
    row_id = await _insert_and_get_id(db_session, test_user)

    with pytest.raises((IntegrityError, DBAPIError)):
        await db_session.execute(delete(AdminAuditLogRecord).where(AdminAuditLogRecord.id == row_id))
        await db_session.flush()
