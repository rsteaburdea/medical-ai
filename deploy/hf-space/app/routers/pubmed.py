from fastapi import APIRouter, HTTPException

from app.catalog import resolve_hf_id
from app.schemas import (
    MatchRequest,
    PubMedChatRequest,
    PubMedChatSessionResponse,
    PubMedSearchRequest,
    StartPubMedChatRequest,
)
from app.services import pubmed_chat as pubmed_chat_service
from app.services.pubmed_api import search_pubmed
from app.services.pubmed_matcher import pubmed_matcher

router = APIRouter(prefix="/api/pubmed", tags=["pubmed"])


@router.post("/match")
def match_text(req: MatchRequest):
    hf_id = resolve_hf_id("pubmed-matcher", req.model_id)
    if not hf_id:
        raise HTTPException(status_code=400, detail="Unknown matcher model")
    try:
        return pubmed_matcher.match(req.text, model=hf_id, top_k=req.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/search")
async def pubmed_search(req: PubMedSearchRequest):
    try:
        articles = await search_pubmed(req.query, retmax=req.retmax)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PubMed search failed: {exc}") from exc
    return {"query": req.query, "articles": articles}


@router.post("/chat/start", response_model=PubMedChatSessionResponse)
def start_chat(req: StartPubMedChatRequest):
    try:
        session = pubmed_chat_service.start_session(req.model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize(session)


@router.post("/chat", response_model=PubMedChatSessionResponse)
async def chat(req: PubMedChatRequest):
    try:
        session = await pubmed_chat_service.chat(
            req.session_id,
            req.message,
            search_query=req.search_query,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _serialize(session)


def _serialize(session) -> PubMedChatSessionResponse:
    return PubMedChatSessionResponse(
        session_id=session.session_id,
        model_id=session.model_id,
        messages=[{"role": m.role, "content": m.content} for m in session.messages],
        last_articles=session.last_articles,
    )
