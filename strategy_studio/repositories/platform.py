from __future__ import annotations

"""平台运行状态仓储。"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from strategy_studio.db.models import PlatformHeartbeat


def utc_now() -> datetime:
    return datetime.now(UTC)


def upsert_platform_heartbeat(
    session: Session,
    service_name: str,
    *,
    status: str,
    pid: int,
    details: dict[str, object] | None = None,
) -> PlatformHeartbeat:
    heartbeat = session.scalars(select(PlatformHeartbeat).where(PlatformHeartbeat.service_name == service_name)).first()
    now = utc_now()
    if heartbeat is None:
        heartbeat = PlatformHeartbeat(
            service_name=service_name,
            status=status,
            pid=pid,
            started_at=now,
            last_seen_at=now,
            details_json=details or {},
        )
        session.add(heartbeat)
        session.flush()
        return heartbeat
    heartbeat.status = status
    heartbeat.pid = pid
    heartbeat.last_seen_at = now
    heartbeat.details_json = details or {}
    session.flush()
    return heartbeat


def list_platform_heartbeats(session: Session) -> list[PlatformHeartbeat]:
    return session.scalars(select(PlatformHeartbeat).order_by(PlatformHeartbeat.service_name)).all()
