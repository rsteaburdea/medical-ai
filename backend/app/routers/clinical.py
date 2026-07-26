from fastapi import APIRouter, HTTPException

from app.schemas import (
    ClinicalChatRequest,
    ClinicalScoreRequest,
    ClinicalSessionResponse,
    GenerateCaseRequest,
    StartClinicalRequest,
)
from app.services import clinical as clinical_service

router = APIRouter(prefix="/api/clinical", tags=["clinical"])


@router.get("/cases")
def list_cases():
    return {"cases": clinical_service.list_cases()}


@router.post("/cases/generate")
def generate_case(req: GenerateCaseRequest):
    try:
        case = clinical_service.generate_case(req.model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"case": case}


@router.post("/start", response_model=ClinicalSessionResponse)
def start(req: StartClinicalRequest):
    try:
        session = clinical_service.start_session(req.model_id, req.case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize(session)


@router.post("/chat", response_model=ClinicalSessionResponse)
def chat(req: ClinicalChatRequest):
    try:
        session = clinical_service.continue_chat(req.session_id, req.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _serialize(session)


@router.post("/score")
def score(req: ClinicalScoreRequest):
    try:
        return clinical_service.score_session(req.session_id, req.final_answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _serialize(session) -> ClinicalSessionResponse:
    return ClinicalSessionResponse(
        session_id=session.session_id,
        model_id=session.model_id,
        case={
            "id": session.case["id"],
            "title": session.case["title"],
            "stem": session.case["stem"],
        },
        messages=[{"role": m.role, "content": m.content} for m in session.messages],
        suggested_questions=session.suggested_questions,
        phase=session.phase,
    )
