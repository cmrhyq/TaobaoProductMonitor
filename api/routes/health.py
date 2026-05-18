"""
Health check endpoint.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """Application health check."""
    return {"status": "ok", "service": "TaobaoProductMonitor"}
