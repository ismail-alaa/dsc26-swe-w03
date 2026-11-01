from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                         prefix="sqlalchemy.", poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
