from fastapi import APIRouter, HTTPException

from app.catalog import AGENTS, get_agent
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "hf_token_configured": bool(settings.hf_token)
        and not settings.hf_token.strip().startswith("hf_your_token"),
        "demo_mode": settings.use_demo,
    }


@router.get("/agents")
def list_agents():
    return {"agents": [a.model_dump() for a in AGENTS]}


@router.get("/agents/{agent_id}")
def agent_detail(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()
