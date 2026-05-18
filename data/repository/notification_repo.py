"""
Notification repository - data access for the notification_log table.
"""

from typing import Optional

import structlog

from data.database import get_session
from data.models import NotificationLog

logger = structlog.get_logger(__name__)


class NotificationRepository:
    """Data access for notification_log table using SQLAlchemy ORM."""

    def insert_notification(
        self,
        product_id: int,
        rule_id: Optional[int],
        notify_type: str,
        notify_target: str,
        notify_content: str,
        notify_status: int = 1,
    ) -> Optional[int]:
        """Record a notification attempt."""
        try:
            with get_session() as session:
                log = NotificationLog(
                    product_id=product_id,
                    rule_id=rule_id,
                    notify_type=notify_type,
                    notify_target=notify_target,
                    notify_content=notify_content,
                    notify_status=notify_status,
                )
                session.add(log)
                session.flush()
                return log.log_id
        except Exception as e:
            logger.error("Insert notification failed", error=str(e))
            return None

    def query_recent_notifications(self, product_id: int, limit: int = 10) -> list[dict]:
        """Get recent notifications for a product."""
        with get_session() as session:
            records = (
                session.query(NotificationLog)
                .filter(NotificationLog.product_id == product_id)
                .order_by(NotificationLog.sent_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "log_id": r.log_id,
                    "product_id": r.product_id,
                    "rule_id": r.rule_id,
                    "notify_type": r.notify_type,
                    "notify_target": r.notify_target,
                    "notify_content": r.notify_content,
                    "notify_status": r.notify_status,
                    "sent_at": r.sent_at,
                }
                for r in records
            ]
