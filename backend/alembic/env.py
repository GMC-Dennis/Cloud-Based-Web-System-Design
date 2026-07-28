from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.db import Base

# Import every module's ORM models so they register on Base.metadata --
# Alembic's autogenerate (and `create_all`-style tooling) needs the full
# metadata assembled from all four bounded contexts, not just whichever
# happened to be imported by whatever ran first.
from app.modules.identity.infrastructure import models as identity_models  # noqa: F401
from app.modules.ledger.infrastructure import models as ledger_models  # noqa: F401
from app.modules.chama.infrastructure import models as chama_models  # noqa: F401
from app.modules.scoring.infrastructure import models as scoring_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    # Migrations run synchronously (psycopg2) even though the app talks to
    # Postgres via asyncpg at runtime -- Alembic's autogenerate machinery
    # doesn't support an async DBAPI.
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
