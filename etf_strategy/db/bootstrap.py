from __future__ import annotations

"""数据库初始化与迁移执行。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy.engine import make_url

from etf_strategy.db.settings import load_platform_settings


def create_database_if_missing() -> str:
    """确保项目数据库存在。"""
    settings = load_platform_settings()
    target_url = make_url(settings.database.url)
    database_name = target_url.database
    if not database_name:
        raise ValueError("数据库 URL 缺少数据库名。")

    admin_url = target_url.set(drivername="postgresql", database=settings.database.admin_database)
    with connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
        row = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)).fetchone()
        if row is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    return database_name


def run_migrations() -> None:
    """执行 Alembic 迁移。"""
    settings = load_platform_settings()
    config = Config(str(Path("alembic.ini").resolve()))
    config.set_main_option("sqlalchemy.url", settings.database.url)
    command.upgrade(config, "head")


def initialize_database() -> str:
    """创建数据库并执行迁移。"""
    database_name = create_database_if_missing()
    run_migrations()
    return database_name
