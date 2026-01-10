import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ruff: noqa: E402, I001 (Alembic env.py requires imports after config setup)

# Load environment variables from .env file
# This ensures DATABASE_URL and other settings are available
try:
    from dotenv import load_dotenv

    # Find .env file in the backend directory or parent directories
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not available, rely on system environment
    pass

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get DATABASE_URL from environment variable
# This is the PRIMARY way to configure the database URL
# Default to SQLite if not set
database_url = os.getenv("DATABASE_URL", "sqlite:///./intentui.db")
config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
# for 'autogenerate' support

# Import Base and all models so they register with metadata
# Note: There are two separate Base classes in the codebase:
# 1. app.database.Base (main models: Canvas, Node, Edge, Preferences, Backup, Job, JobArtifact)
# 2. app.models.intent.Base (intent models: UserIntent, AttachmentDB, AssumptionResolutionDB)
# noqa: E402 (imports must be after config setup for Alembic env.py)
from app.database import Base as MainBase  # noqa: F401 (registers metadata)
from app.models.artifact import JobArtifact  # noqa: F401 (registers metadata)
from app.models.backup import Backup  # noqa: F401 (registers metadata)
from app.models.canvas import Canvas, Edge, Node  # noqa: F401 (registers metadata)
from app.models.job import Job  # noqa: F401 (registers metadata)
from app.models.preferences import Preferences  # noqa: F401 (registers metadata)
from app.mcp.models import MCPServer, MCPExecutionLog  # noqa: F401 (registers metadata)

# Intent models use a separate Base
from app.models.intent import (  # noqa: E402, F401 (registers metadata)
    AttachmentDB,
    AssumptionResolutionDB,
    Base as IntentBase,
    UserIntent,
)

# Combine metadata from both Base classes for Alembic autogenerate
from sqlalchemy.schema import MetaData  # noqa: E402

target_metadata = MetaData()
for table in MainBase.metadata.tables.values():
    target_metadata._add_table(table.name, table.schema, table)
for table in IntentBase.metadata.tables.values():
    target_metadata._add_table(table.name, table.schema, table)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable must be set for migrations"
        )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    url = configuration.get("sqlalchemy.url")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable must be set for migrations"
        )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
