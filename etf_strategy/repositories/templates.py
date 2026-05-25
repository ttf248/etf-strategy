from __future__ import annotations

"""策略参数模板仓储。"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from etf_strategy.db.models import StrategyParameterTemplate


def list_strategy_templates(
    session: Session,
    strategy_kind: str | None = None,
    interval: str | None = None,
    active_only: bool = False,
) -> list[StrategyParameterTemplate]:
    statement = select(StrategyParameterTemplate)
    if strategy_kind:
        statement = statement.where(StrategyParameterTemplate.strategy_kind == strategy_kind)
    if interval:
        statement = statement.where(StrategyParameterTemplate.interval == interval)
    if active_only:
        statement = statement.where(StrategyParameterTemplate.is_active.is_(True))
    statement = statement.order_by(
        StrategyParameterTemplate.strategy_kind,
        StrategyParameterTemplate.interval,
        StrategyParameterTemplate.is_default.desc(),
        StrategyParameterTemplate.template_name,
    )
    return session.scalars(statement).all()


def get_strategy_template(session: Session, template_id: int) -> StrategyParameterTemplate | None:
    return session.get(StrategyParameterTemplate, template_id)


def get_strategy_template_by_key(session: Session, template_key: str) -> StrategyParameterTemplate | None:
    return session.scalars(select(StrategyParameterTemplate).where(StrategyParameterTemplate.template_key == template_key)).first()


def create_strategy_template(session: Session, payload: dict[str, object]) -> StrategyParameterTemplate:
    template = StrategyParameterTemplate(**payload)
    session.add(template)
    session.flush()
    return template


def update_strategy_template(
    session: Session,
    template: StrategyParameterTemplate,
    payload: dict[str, object],
) -> StrategyParameterTemplate:
    for key, value in payload.items():
        setattr(template, key, value)
    session.flush()
    return template


def clear_default_template_flag(
    session: Session,
    strategy_kind: str,
    interval: str,
    exclude_id: int | None = None,
) -> None:
    statement = (
        update(StrategyParameterTemplate)
        .where(
            StrategyParameterTemplate.strategy_kind == strategy_kind,
            StrategyParameterTemplate.interval == interval,
            StrategyParameterTemplate.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if exclude_id is not None:
        statement = statement.where(StrategyParameterTemplate.id != exclude_id)
    session.execute(statement)
