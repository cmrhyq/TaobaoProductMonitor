"""
Monitor rule repository - data access for the monitor_rules table.
"""

from typing import Optional

import structlog

from data.database import get_session
from data.models import MonitorRule

logger = structlog.get_logger(__name__)


class RuleRepository:
    """Data access for monitor_rules table using SQLAlchemy ORM."""

    def get_active_rules(self, product_id: int) -> list[dict]:
        """Get all active monitoring rules for a product."""
        with get_session() as session:
            rules = (
                session.query(MonitorRule)
                .filter(MonitorRule.product_id == product_id, MonitorRule.is_active == 1)
                .all()
            )
            return [
                {
                    "rule_id": r.rule_id,
                    "rule_type": r.rule_type,
                    "threshold_value": r.threshold_value,
                    "threshold_percent": r.threshold_percent,
                }
                for r in rules
            ]

    def insert_rule(
        self,
        product_id: int,
        rule_type: str = "absolute_drop",
        threshold_value: Optional[float] = None,
        threshold_percent: Optional[float] = None,
    ) -> Optional[int]:
        """Create a new monitoring rule."""
        try:
            with get_session() as session:
                rule = MonitorRule(
                    product_id=product_id,
                    rule_type=rule_type,
                    threshold_value=threshold_value,
                    threshold_percent=threshold_percent,
                )
                session.add(rule)
                session.flush()
                return rule.rule_id
        except Exception as e:
            logger.error("Insert rule failed", error=str(e))
            return None

    def deactivate_rule(self, rule_id: int) -> bool:
        """Deactivate a monitoring rule."""
        try:
            with get_session() as session:
                rows = (
                    session.query(MonitorRule)
                    .filter(MonitorRule.rule_id == rule_id)
                    .update({MonitorRule.is_active: 0})
                )
                return rows > 0
        except Exception as e:
            logger.error("Deactivate rule failed", error=str(e))
            return False
