from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool, MetaData
from alembic import context

# Import ALL service models to ensure complete metadata coverage
from api_studio.models import Base as ApiStudioBase
from universal_webhook.models import Base as UniversalWebhookBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine metadata from all services
# This allows a single alembic config to manage migrations for multiple databases
target_metadata = MetaData()

# Merge all model metadata
for base in [ApiStudioBase, UniversalWebhookBase]:
    for table in base.metadata.tables.values():
        table.tometadata(target_metadata)


def get_database_url():
    """
    Get database URL from environment or config.

    Priority:
    1. DATABASE_URL environment variable (allows targeting specific database)
    2. sqlalchemy.url from alembic.ini (fallback)

    Usage:
        export DATABASE_URL=postgresql+asyncpg://user:pass@host/api_studio
        alembic upgrade head
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Environment variable takes precedence
        return db_url

    # Fallback to config file
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    # Override sqlalchemy.url with environment variable if present
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
