"""Central append-only audit logging."""
from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    request: Request | None = None,
) -> None:
    ip = request.client.host if request and request.client else None
    # Callers must never place credentials or extracted private content in detail.
    db.add(AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=detail or {},
        ip_address=ip,
    ))
