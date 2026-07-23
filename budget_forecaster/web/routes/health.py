"""Health check, public (no auth), for uptime probes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Return a liveness marker."""
    return {"status": "ok"}
