import os
import sys
import tempfile
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Bootstrapper to resolve 'backend' package import issues when running inside Docker container.
current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
backend_dir = None
while current_dir and current_dir != '/':
    if os.path.exists(os.path.join(current_dir, 'database.py')):
        backend_dir = current_dir
        break
    current_dir = os.path.dirname(current_dir)
if not backend_dir:
    backend_dir = '/app'

if os.path.basename(backend_dir) != 'backend':
    tmp_dir = os.path.join(tempfile.gettempdir(), 'family_tree_backend_path')
    os.makedirs(tmp_dir, exist_ok=True)
    symlink_path = os.path.join(tmp_dir, 'backend')
    if not os.path.exists(symlink_path):
        try:
            os.symlink(backend_dir, symlink_path)
        except Exception:
            pass
    if tmp_dir not in sys.path:
        sys.path.insert(0, tmp_dir)

# Add parent directory of backend (i.e. the project root) to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlmodel import SQLModel
# Import all models to ensure SQLModel.metadata is fully populated
from backend.models import (
    Member, User, FamilyGroup, MemberFamilyLink, UserFamilyRole,
    AuditLog, SourceRecord, Citation, ReviewRequest, SiteSetting
)
import backend.main as main

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target metadata for 'autogenerate' support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = main.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = main.DATABASE_URL
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
