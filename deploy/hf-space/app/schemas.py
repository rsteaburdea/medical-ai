from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StartClinicalRequest(BaseModel):
    model_id: str
    case_id: str | None = None


class GenerateCaseRequest(BaseModel):
    model_id: str


class ClinicalChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)


class ClinicalScoreRequest(BaseModel):
    session_id: str
    final_answer: str | None = None


class MatchRequest(BaseModel):
    text: str = Field(min_length=20, description="Paragraph or abstract fragment to match")
    model_id: str = "pubmedbert-embeddings"
    top_k: int = Field(default=3, ge=1, le=10)


class StartPubMedChatRequest(BaseModel):
    model_id: str


class PubMedChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)
    search_query: str | None = None


class PubMedSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    retmax: int = Field(default=5, ge=1, le=20)


class ApiMessage(BaseModel):
    role: str
    content: str


class ClinicalSessionResponse(BaseModel):
    session_id: str
    model_id: str
    case: dict[str, Any]
    messages: list[ApiMessage]
    suggested_questions: list[str]
    phase: str


class PubMedChatSessionResponse(BaseModel):
    session_id: str
    model_id: str
    messages: list[ApiMessage]
    last_articles: list[dict[str, Any]] = []
