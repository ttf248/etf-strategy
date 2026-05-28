from __future__ import annotations

"""数据库引擎与会话工厂。"""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from strategy_studio.db.settings import load_platform_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = load_platform_settings()
    return create_engine(settings.database.url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def open_session() -> Session:
    return get_session_factory()()

