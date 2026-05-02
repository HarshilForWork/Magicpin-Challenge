from fastapi import APIRouter

from core.config import settings

router = APIRouter()


@router.get("/v1/metadata")
async def metadata():
    return {
        "team_name": settings["app"]["team_name"],
        "team_members": settings["app"]["team_members"],
        "model": settings["llm"]["model"],
        "approach": "filter-first composer with TOON context serialization (python-toon), Groq inference, MLflow logging",
        "contact_email": settings["app"]["contact_email"],
        "version": settings["app"]["version"],
        "submitted_at": "2026-04-26T08:00:00Z",
    }
