from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.catalog import get_model, resolve_hf_id
from app.config import get_settings
from app.services.hf_client import hf_service
from app.services.pubmed_api import format_articles_context, search_pubmed

SYSTEM_PROMPT = """You are a biomedical literature assistant specialised in PubMed.
You help clinicians and researchers: find papers, summarise abstracts, compare findings,
explain methods, and draft grounded scientific text.

Rules:
- Prefer claims supported by the provided PubMed context; cite PMIDs when possible.
- If evidence is weak or missing, say so clearly.
- Be concise and clinically useful.
- When asked to generate new content, label it as draft / educational, not peer-reviewed fact.
- Never invent PMIDs.
"""


class ChatMessage(BaseModel):
    role: str
    content: str


class PubMedChatSession(BaseModel):
    session_id: str
    model_id: str
    hf_model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    last_articles: list[dict[str, Any]] = Field(default_factory=list)


_sessions: dict[str, PubMedChatSession] = {}


def start_session(model_id: str) -> PubMedChatSession:
    hf_model = resolve_hf_id("pubmed-chat", model_id)
    if not hf_model:
        raise ValueError(f"Unknown pubmed chat model: {model_id}")

    model_meta = get_model("pubmed-chat", model_id)
    opener = (
        "PubMed Literature Chat is ready.\n\n"
        "Type a question below (or use a suggestion), optionally add a PubMed search query, "
        "then press Send — I will answer using retrieved abstracts when available.\n\n"
        f"Model: {model_meta.name if model_meta else model_id}"
    )

    session = PubMedChatSession(
        session_id=str(uuid.uuid4()),
        model_id=model_id,
        hf_model=hf_model,
        messages=[
            ChatMessage(
                role="assistant",
                content=opener,
            )
        ],
    )
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> PubMedChatSession | None:
    return _sessions.get(session_id)


async def chat(
    session_id: str,
    user_message: str,
    *,
    search_query: str | None = None,
) -> PubMedChatSession:
    session = _sessions.get(session_id)
    if not session:
        raise KeyError("Session not found")

    articles: list[dict[str, Any]] = []
    query = search_query
    if not query and _looks_like_search(user_message):
        query = user_message

    if query:
        try:
            articles = await search_pubmed(query, retmax=5)
            session.last_articles = articles
        except Exception:
            articles = session.last_articles

    session.messages.append(ChatMessage(role="user", content=user_message))

    context = format_articles_context(articles or session.last_articles)
    llm_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current PubMed context:\n{context}"},
    ]
    for m in session.messages[-20:]:
        llm_messages.append({"role": m.role, "content": m.content})

    if get_settings().use_demo:
        reply = _demo_literature_reply(user_message, articles or session.last_articles)
    else:
        try:
            reply = hf_service.chat(session.hf_model, llm_messages, max_tokens=900, temperature=0.4)
        except RuntimeError:
            reply = _demo_literature_reply(user_message, articles or session.last_articles)

    session.messages.append(ChatMessage(role="assistant", content=reply))
    return session


def _demo_literature_reply(user_message: str, articles: list[dict[str, Any]]) -> str:
    if articles:
        lines = [
            "Here is a grounded summary from the retrieved PubMed abstracts "
            "(demo mode — set HF_TOKEN for live Llama 3.1 / Qwen generation):\n"
        ]
        for a in articles[:3]:
            abstract = (a.get("abstract") or "")[:280]
            lines.append(
                f"- **PMID {a.get('pmid')}** — {a.get('title')}\n  {abstract}…"
            )
        lines.append(f"\nYour question: _{user_message}_")
        lines.append(
            "\nNext step in live mode: ask me to compare methods, draft a paragraph, or deepen one PMID."
        )
        return "\n".join(lines)
    return (
        "Demo mode: I can search PubMed without a Hugging Face token, but generative chat "
        "needs `HF_TOKEN` in `backend/.env`.\n\n"
        "Try a short topic in the search box (e.g. `anastomotic leak colorectal`) then ask "
        "me to summarise."
    )


def _looks_like_search(text: str) -> bool:
    lower = text.lower().strip()
    triggers = (
        "find papers",
        "search pubmed",
        "search for",
        "articles about",
        "papers on",
        "literature on",
        "recent studies",
    )
    return any(t in lower for t in triggers) or (len(lower.split()) <= 8 and "?" not in lower)
