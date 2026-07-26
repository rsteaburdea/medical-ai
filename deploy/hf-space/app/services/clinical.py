from __future__ import annotations

import json
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.catalog import resolve_hf_id
from app.config import get_settings
from app.services.clinical_answers import build_answer_bank, instant_answer
from app.services.hf_client import extract_json_block, hf_service

CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "clinical_cases.json"


@lru_cache
def _load_builtin_cases() -> tuple[dict[str, Any], ...]:
    with CASES_PATH.open(encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list) or len(cases) < 1:
        raise RuntimeError(f"No clinical cases found in {CASES_PATH}")
    return tuple(cases)


CLINICAL_CASES: list[dict[str, Any]] = list(_load_builtin_cases())


SYSTEM_PROMPT = """You are an examiner running a Core Surgical Training (CST) clinical case station \
for the Irish surgical training pathway (RCSI-style). You are professional, concise, and fair.

Rules:
- Present and run ONE clinical case as an interviewer / simulated patient source of truth.
- Answer the candidate's history and examination questions with realistic clinical information only.
- Do NOT volunteer the diagnosis. Let the candidate work it out.
- Do NOT coach with numbered "Next steps", management checklists, or teaching plans during the viva. \
Only give clinical findings / investigation results the candidate asked for.
- After EVERY candidate turn, replace suggested_questions with 4–5 NEW short question cards that:
  1. Were NOT already asked in the transcript (never repeat prior cards or user questions).
  2. Dig one step deeper toward the correct diagnosis and a safe management plan.
  3. Progress the station: deepen history → examination → investigations → commit diagnosis/plan.
  4. Prefer questions that elicit still-missing key clinical features (without naming the diagnosis).
  5. Differ clearly from the previous suggested_questions list — always a fresh set.
- Keep replies tight (max ~80 words of clinical content) plus the structured JSON trailer.
- Score only when asked to finalise; until then stay in examiner mode.

Always end your reply with a JSON block on its own after the prose, in this exact shape:
{"suggested_questions":["...","...","...","...","..."],"phase":"history|examination|investigations|management|closing","hint_level":0}
hint_level is 0-2 (how much you have nudged).
"""

SCORE_PROMPT = """You are a strict CST (Core Surgical Training) clinical station examiner.

Return ONLY valid JSON:
{
  "overall_score": 0-100,
  "subscores": {
    "history_taking": 0-100,
    "clinical_reasoning": 0-100,
    "diagnosis": 0-100,
    "management": 0-100,
    "communication": 0-100
  },
  "what_went_well": ["..."],
  "gaps": ["..."],
  "better_answers": [
    {"topic":"...", "candidate_said":"...", "stronger_answer":"...", "why":"..."}
  ],
  "ideal_summary": "2-4 sentence model answer a strong CST candidate would give",
  "ideal_diagnosis": "the true diagnosis for this case",
  "candidate_diagnosis": "what the candidate committed to, or null if none",
  "diagnosis_stated": true,
  "diagnosis_proximity": "exact|near_miss|same_region|same_system|distant|none",
  "questions_to_correct": 0,
  "pass_likely": true,
  "model_conversation": [
    {"role":"assistant","content":"..."},
    {"role":"user","content":"..."}
  ]
}

DIAGNOSIS RUBRIC (mandatory — apply before overall_score):
1) NO explicit working diagnosis in the transcript → diagnosis ≤ 15, overall ≤ 45, pass_likely=false,
   diagnosis_proximity="none", candidate_diagnosis=null.
2) CORRECT / synonym of ideal_diagnosis → diagnosis 85–100; proximity="exact".
3) NEAR MISS (closely related differential, same presentation, e.g. mesenteric adenitis vs appendicitis;
   biliary colic vs cholecystitis) → diagnosis 55–75; proximity="near_miss".
4) SAME BODY REGION / anatomical area but wrong disease → diagnosis 35–55; proximity="same_region".
5) SAME SYSTEM (e.g. GI vs GI) but different region/pathology → diagnosis 20–40; proximity="same_system".
6) DISTANT / unrelated system → diagnosis ≤ 20; proximity="distant". Wrong diagnosis also caps overall:
   near_miss ≤ 75, same_region ≤ 65, same_system ≤ 55, distant ≤ 45.

questions_to_correct: estimate how many focused follow-up questions the candidate still needed
to reach the correct diagnosis (0 if already correct; typically 1–6). Higher = more incomplete work-up.
If questions_to_correct ≥ 4 and diagnosis wrong/absent, reduce clinical_reasoning by ~15.

Management without a diagnosis cannot score above 50. History/communication can still be high if
the viva was structured.

model_conversation: exemplar viva (8–14 turns) scoring ~100/100 with the TRUE diagnosis.
Do not invent a different diagnosis than the case key.
"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ClinicalSession(BaseModel):
    session_id: str
    model_id: str
    hf_model: str
    case: dict[str, Any]
    messages: list[ChatMessage] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    phase: str = "history"
    answer_bank: dict[str, str] = Field(default_factory=dict)


# In-memory sessions (fine for demo / single-server deploy)
_sessions: dict[str, ClinicalSession] = {}
_extra_cases: list[dict[str, Any]] = []


def _all_cases() -> list[dict[str, Any]]:
    return [*CLINICAL_CASES, *_extra_cases]


def list_cases() -> list[dict[str, Any]]:
    """Public case cards for the picker (no diagnosis spoilers)."""
    return [
        {
            "id": c["id"],
            "title": c["title"],
            "stem": c["stem"],
            "generated": c.get("generated", False),
        }
        for c in _all_cases()
    ]


def _pick_case(case_id: str | None) -> dict[str, Any]:
    if case_id:
        for c in _all_cases():
            if c["id"] == case_id:
                return c
    import random

    return random.choice(_all_cases())


GENERATE_CASE_PROMPT = """You generate Core Surgical Training (CST) clinical case stations \
for the Irish surgical training pathway (RCSI-style).

Return ONLY valid JSON with this shape:
{
  "id": "short-kebab-slug",
  "title": "Short presenting complaint title",
  "stem": "Full examiner-style case stem including age/sex, history, key signs and vitals. 4-7 sentences.",
  "ideal_diagnosis": "Most likely diagnosis",
  "key_features": ["feature1", "feature2", "feature3", "feature4"],
  "suggested_questions": ["q1", "q2", "q3", "q4", "q5"]
}

Rules:
- Acute surgical / emergency / clinic cases suitable for CST viva.
- Do NOT reveal the diagnosis in the stem or title.
- Make vitals and findings realistic.
- Avoid duplicating the topic: __AVOID__
"""


def generate_case(model_id: str, avoid_topics: list[str] | None = None) -> dict[str, Any]:
    hf_model = resolve_hf_id("clinical-station", model_id)
    if not hf_model:
        raise ValueError(f"Unknown clinical model: {model_id}")

    avoid = ", ".join(avoid_topics or [c["title"] for c in _all_cases()][-8:])
    prompt = GENERATE_CASE_PROMPT.replace("__AVOID__", avoid or "none")

    if get_settings().use_demo:
        case = _demo_generated_case()
    else:
        raw = hf_service.chat(
            hf_model,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate one new CST clinical case card now."},
            ],
            max_tokens=700,
            temperature=0.7,
        )
        parsed = extract_json_block(raw)
        if not parsed or not parsed.get("title") or not parsed.get("stem"):
            case = _demo_generated_case()
        else:
            case = {
                "id": str(parsed.get("id") or f"gen-{uuid.uuid4().hex[:8]}"),
                "title": str(parsed["title"]).strip(),
                "stem": str(parsed["stem"]).strip(),
                "ideal_diagnosis": str(parsed.get("ideal_diagnosis") or "Clinical diagnosis TBC").strip(),
                "key_features": [str(x) for x in (parsed.get("key_features") or [])][:6] or [
                    "Focused history",
                    "Key examination findings",
                    "Appropriate investigations",
                    "Safe initial management",
                ],
                "suggested_questions": [str(x) for x in (parsed.get("suggested_questions") or [])][:5]
                or [
                    "Onset and character of symptoms?",
                    "Associated symptoms?",
                    "Past surgical history?",
                    "Medications and allergies?",
                    "May I examine the relevant system?",
                ],
                "generated": True,
            }

    # ensure unique id
    existing = {c["id"] for c in _all_cases()}
    if case["id"] in existing:
        case["id"] = f"{case['id']}-{uuid.uuid4().hex[:4]}"
    case["generated"] = True
    _extra_cases.insert(0, case)
    return {
        "id": case["id"],
        "title": case["title"],
        "stem": case["stem"],
        "generated": True,
    }


def _demo_generated_case() -> dict[str, Any]:
    n = len(_extra_cases) + 1
    return {
        "id": f"gen-demo-{uuid.uuid4().hex[:6]}",
        "title": f"Epigastric pain after NSAIDs ({n})",
        "stem": (
            "A 49-year-old man presents with sudden severe epigastric pain that began 3 hours ago. "
            "He has been taking high-dose ibuprofen for backache. The abdomen is rigid with "
            "generalised peritonism. HR 118, BP 96/60, Temp 37.4°C. An erect chest X-ray is pending."
        ),
        "ideal_diagnosis": "Perforated peptic ulcer",
        "key_features": [
            "Sudden severe epigastric pain",
            "NSAID use",
            "Board-like rigidity / peritonitis",
            "Free air under diaphragm (expected)",
        ],
        "suggested_questions": [
            "Any previous dyspepsia or ulcer disease?",
            "Haematemesis or melaena?",
            "Anticoagulants or steroids?",
            "Last oral intake?",
            "May I see the erect chest X-ray?",
        ],
        "generated": True,
    }


def start_session(model_id: str, case_id: str | None = None) -> ClinicalSession:
    hf_model = resolve_hf_id("clinical-station", model_id)
    if not hf_model:
        raise ValueError(f"Unknown clinical model: {model_id}")

    case = _pick_case(case_id)
    bank = build_answer_bank(case)
    session = ClinicalSession(
        session_id=str(uuid.uuid4()),
        model_id=model_id,
        hf_model=hf_model,
        case=case,
        suggested_questions=list(case["suggested_questions"][:5]),
        phase="history",
        answer_bank=bank,
    )

    opener = (
        f"{case['stem']}\n\n"
        "Please take a focused history. You may ask questions or select a question card. "
        "When ready, state your working diagnosis and initial management plan."
    )
    session.messages.append(ChatMessage(role="assistant", content=opener))
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> ClinicalSession | None:
    return _sessions.get(session_id)


def _norm_q(text: str) -> str:
    return " ".join(text.lower().split()).rstrip("?.!")


def _asked_questions(session: ClinicalSession) -> set[str]:
    asked = {_norm_q(m.content) for m in session.messages if m.role == "user"}
    for prev in session.suggested_questions:
        # Current cards become stale once the candidate picks one — exclude them from the next set
        # only when they were already asked; keep unused ones available as fillers below.
        if _norm_q(prev) in asked:
            asked.add(_norm_q(prev))
    return asked


def _phase_after_turn(session: ClinicalSession, user_message: str, inferred: str | None = None) -> str:
    q = user_message.lower()
    if any(
        w in q
        for w in (
            "diagnos",
            "impression",
            "management plan",
            "working diagnosis",
            "i think this is",
            "my plan is",
            "definitive treatment",
        )
    ):
        return "management"
    if any(w in q for w in ("blood", "wcc", "crp", "imaging", "ct", "ultrasound", "x-ray", "investigat", "lactate")):
        return "investigations"
    if any(w in q for w in ("exam", "tender", "abdomen", "scrot", "pulse", "leg", "palpat", "auscult")):
        return "examination"
    if inferred in {"history", "examination", "investigations", "management", "closing"}:
        return inferred
    user_turns = sum(1 for m in session.messages if m.role == "user")
    if user_turns <= 2:
        return "history"
    if user_turns <= 4:
        return "examination"
    if user_turns <= 6:
        return "investigations"
    return "management"


def _progressive_suggested_questions(
    session: ClinicalSession,
    phase: str,
    *,
    llm_questions: list[str] | None = None,
    exclude_extra: list[str] | None = None,
) -> list[str]:
    """Build a fresh card set that advances toward diagnosis without repeating asked items."""
    asked = _asked_questions(session)
    for extra in exclude_extra or []:
        asked.add(_norm_q(extra))
    # Also exclude the just-used card set so the sidebar always feels refreshed
    for prev in session.suggested_questions:
        asked.add(_norm_q(prev))

    case_qs = [str(q) for q in (session.case.get("suggested_questions") or [])]

    by_phase: dict[str, list[str]] = {
        "history": [
            *case_qs,
            "When did this start and how has it progressed?",
            "Any fever, anorexia, or vomiting?",
            "Any urinary or bowel symptoms?",
            "Past surgical / medical history and medications?",
            "Any red-flag symptoms I should ask about?",
            "What makes the pain better or worse?",
        ],
        "examination": [
            "May I examine the relevant system now?",
            "Any focal tenderness, rebound, or guarding?",
            "What are the current vital signs?",
            "Any hernia, scrotal, or vascular findings to check?",
            "Any peritonism or masses?",
            *case_qs,
        ],
        "investigations": [
            "I would like bloods: FBC, CRP, U&E (and β-hCG if relevant).",
            "What imaging is most appropriate next?",
            "Any results that change the urgency?",
            "Do we need blood gas / lactate?",
            "Anything else before I commit to a diagnosis?",
        ],
        "management": [
            "My working diagnosis is… (state it clearly).",
            "Immediate plan: ABC, IV access, analgesia, NPO.",
            "Who needs senior / specialty review now?",
            "What is the definitive treatment pathway?",
            "Any antibiotics or resuscitation steps before transfer?",
        ],
        "closing": [
            "State your final diagnosis with supporting features.",
            "Summarise immediate management and escalation.",
            "Any safety-net advice if observation is chosen?",
        ],
    }

    order = {
        "history": ["history", "examination", "investigations", "management"],
        "examination": ["examination", "investigations", "management", "history"],
        "investigations": ["investigations", "management", "examination", "history"],
        "management": ["management", "closing", "investigations", "examination"],
        "closing": ["closing", "management"],
    }.get(phase, ["history", "examination", "investigations", "management"])

    pool: list[str] = []
    for p in order:
        pool.extend(by_phase.get(p, []))
    if llm_questions:
        # Prefer model suggestions first when they are new
        pool = [str(q) for q in llm_questions] + pool

    out: list[str] = []
    seen: set[str] = set()
    for q in pool:
        n = _norm_q(q)
        if not n or n in asked or n in seen:
            continue
        seen.add(n)
        out.append(q.strip())
        if len(out) >= 5:
            break

    # Absolute fallback so the UI never goes empty
    if len(out) < 3:
        for q in [
            "What examination finding would change your next step?",
            "Which investigation confirms or refutes your top differential?",
            "State your working diagnosis and initial management.",
        ]:
            n = _norm_q(q)
            if n not in seen:
                out.append(q)
                seen.add(n)
            if len(out) >= 5:
                break
    return out[:5]


def _demo_reply(session: ClinicalSession, user_message: str) -> tuple[str, list[str], str]:
    """Fast rule-based examiner (also used when HF Inference is unavailable)."""
    phase = _phase_after_turn(session, user_message)
    prose = instant_answer(session.case, user_message, session.answer_bank or None)
    if not prose:
        prose = "Thank you. Please continue your focused history or examination."
    if phase == "management" and re.search(
        r"diagnos|impression|my plan|working diagnosis", user_message, flags=re.IGNORECASE
    ):
        prose = (
            "Noted. I will not confirm the diagnosis yet — please commit to your working diagnosis "
            "and initial management, then use End & score for formal feedback."
        )

    next_q = _progressive_suggested_questions(
        session, phase, exclude_extra=[user_message]
    )
    return prose, next_q, phase


def _model_conversation_for_case(case: dict[str, Any]) -> list[dict[str, str]]:
    title = case["title"]
    stem = case["stem"]
    dx = case["ideal_diagnosis"]
    features = case.get("key_features") or []
    qs = case.get("suggested_questions") or [
        "Onset and progression of symptoms?",
        "Associated symptoms?",
        "Past surgical / medical history?",
        "May I examine the relevant system?",
        "What investigations would you like?",
    ]
    return [
        {
            "role": "assistant",
            "content": f"{stem}\n\nPlease take a focused history.",
        },
        {"role": "user", "content": qs[0]},
        {
            "role": "assistant",
            "content": "Symptoms began as described in the stem and have progressed as expected for this pathology. No red-flag alternate symptoms so far.",
        },
        {"role": "user", "content": qs[1] if len(qs) > 1 else "Any associated systemic symptoms?"},
        {
            "role": "assistant",
            "content": "Associated features align with the presentation; vitals remain as given. No confounding urinary/GI distractors unless already stated.",
        },
        {"role": "user", "content": qs[2] if len(qs) > 2 else "Any previous surgery or relevant PMH?"},
        {
            "role": "assistant",
            "content": "Past history is consistent with the stem. No additional contraindications to emergency management.",
        },
        {
            "role": "user",
            "content": qs[3] if len(qs) > 3 else "May I examine the patient?",
        },
        {
            "role": "assistant",
            "content": "Examination supports the working diagnosis: findings match key clinical signs for this case.",
        },
        {
            "role": "user",
            "content": qs[4] if len(qs) > 4 else "I would like bloods and appropriate imaging.",
        },
        {
            "role": "assistant",
            "content": "Investigations return results compatible with the diagnosis; nothing suggests an alternate emergency that should supersede this working diagnosis.",
        },
        {
            "role": "user",
            "content": (
                f"My working diagnosis is {dx}. Supporting features: "
                + "; ".join(features)
                + ". Immediate plan: ABC/resuscitation as needed, analgesia, appropriate labs/imaging, "
                "senior surgical review, NPO, and definitive treatment pathway for this diagnosis."
            ),
        },
        {
            "role": "assistant",
            "content": "Clear, structured answer covering diagnosis, supporting features, and safe initial management. That is a model CST response.",
        },
    ]


def continue_chat(session_id: str, user_message: str) -> ClinicalSession:
    session = _sessions.get(session_id)
    if not session:
        raise KeyError("Session not found")

    session.messages.append(ChatMessage(role="user", content=user_message))
    if not session.answer_bank:
        session.answer_bank = build_answer_bank(session.case)

    # Instant path: predefined / suggested cards — no HF round-trip
    cached = instant_answer(session.case, user_message, session.answer_bank)
    if cached:
        phase = _phase_after_turn(session, user_message)
        if phase == "management" and re.search(
            r"diagnos|impression|my plan|working diagnosis", user_message, flags=re.IGNORECASE
        ):
            cached = (
                "Noted. I will not confirm the diagnosis yet — please commit to your working diagnosis "
                "and initial management, then use End & score for formal feedback."
            )
        session.suggested_questions = _progressive_suggested_questions(
            session, phase, exclude_extra=[user_message]
        )
        for q in session.suggested_questions:
            n = _norm_q(q)
            if n not in session.answer_bank:
                hit = instant_answer(session.case, q, session.answer_bank)
                if hit:
                    session.answer_bank[n] = hit
        session.phase = phase
        session.messages.append(ChatMessage(role="assistant", content=cached))
        return session

    if get_settings().use_demo:
        prose, questions, phase = _demo_reply(session, user_message)
        session.suggested_questions = questions
        session.phase = phase
        session.messages.append(ChatMessage(role="assistant", content=prose))
        return session

    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    llm_messages.append(
        {
            "role": "system",
            "content": (
                f"CASE KEY (do not reveal verbatim): diagnosis={session.case['ideal_diagnosis']}; "
                f"key_features={session.case['key_features']}. "
                f"Already asked by candidate (do not re-suggest): "
                f"{[m.content for m in session.messages if m.role == 'user']}. "
                f"Previous suggestion cards to avoid repeating: {session.suggested_questions}."
            ),
        }
    )
    for m in session.messages:
        llm_messages.append({"role": m.role, "content": m.content})

    try:
        raw = hf_service.chat(session.hf_model, llm_messages, max_tokens=500, temperature=0.3)
    except RuntimeError:
        prose, questions, phase = _demo_reply(session, user_message)
        session.suggested_questions = questions
        session.phase = phase
        session.messages.append(ChatMessage(role="assistant", content=prose))
        return session

    parsed = extract_json_block(raw) or {}
    prose = raw
    if parsed:
        idx = raw.rfind("{")
        if idx != -1:
            prose = raw[:idx].strip()

    prose = _strip_coaching(prose or raw)

    phase = _phase_after_turn(session, user_message, str(parsed.get("phase") or "") or None)
    llm_qs = [str(q) for q in (parsed.get("suggested_questions") or []) if str(q).strip()]
    session.suggested_questions = _progressive_suggested_questions(
        session,
        phase,
        llm_questions=llm_qs,
        exclude_extra=[user_message],
    )
    for q in session.suggested_questions:
        n = _norm_q(q)
        if n not in session.answer_bank:
            hit = instant_answer(session.case, q, session.answer_bank)
            if hit:
                session.answer_bank[n] = hit
    session.phase = phase
    session.messages.append(ChatMessage(role="assistant", content=prose or raw))
    return session


def _strip_coaching(text: str) -> str:
    """Remove 'Next steps:' teaching lists that break CST examiner mode."""
    if not text:
        return text
    cut = re.search(r"\n\s*next steps\s*:", text, flags=re.IGNORECASE)
    if cut:
        text = text[: cut.start()].strip()
    if re.search(r"next steps\s*:", text, flags=re.IGNORECASE) and re.search(
        r"^\s*(\d+\.|[-*])\s+", text, flags=re.MULTILINE
    ):
        return "Please ask a focused history or examination question, or state your working diagnosis."
    return text.strip()


def _candidate_transcript(session: ClinicalSession) -> str:
    return " ".join(m.content for m in session.messages if m.role == "user")


def _region_for_diagnosis(text: str) -> str | None:
    t = text.lower()
    regions: list[tuple[str, tuple[str, ...]]] = [
        ("abdomen_rif", ("appendic", "mesenteric adenitis", "ovarian torsion", "ectopic", "meckel")),
        ("abdomen_obstruction", ("obstruction", "sbo", "ileus", "adhes", "volvulus", "intussuscept")),
        ("biliary", ("cholecyst", "cholangitis", "biliary", "gallstone", "choledoch")),
        ("upper_gi", ("ulcer", "perforat", "gastr", "duoden", "boerhaave", "pancreat")),
        ("lower_gi", ("diverticul", "colitis", "gi bleed", "perianal", "abscess", "haemorrh")),
        ("vascular_abdomen", ("aaa", "aortic aneurysm", "mesenteric ischaemia")),
        ("hernia", ("hernia", "inguinal", "femoral", "incisional")),
        ("urogenital", ("torsion", "testicular", "renal colic", "ureteric", "pyelo", "scrot")),
        ("vascular_limb", ("limb ischaemia", "ischemia", "embolus", "compartment")),
        ("soft_tissue", ("necrotis", "fasciitis", "cellulitis", "abscess")),
        ("breast", ("breast", "mastitis")),
        ("endocrine_neck", ("thyroid", "parathyroid", "goitre")),
        ("trauma", ("splenic", "liver laceration", "blunt trauma", "penetrating")),
        ("jaundice_malignancy", ("pancreatic head", "obstructive jaundice", "periampullary")),
    ]
    for name, keys in regions:
        if any(k in t for k in keys):
            return name
    return None


def _system_for_region(region: str | None) -> str | None:
    if not region:
        return None
    mapping = {
        "abdomen_rif": "gi",
        "abdomen_obstruction": "gi",
        "biliary": "gi",
        "upper_gi": "gi",
        "lower_gi": "gi",
        "vascular_abdomen": "vascular",
        "hernia": "gi",
        "urogenital": "urogenital",
        "vascular_limb": "vascular",
        "soft_tissue": "soft_tissue",
        "breast": "breast",
        "endocrine_neck": "endocrine",
        "trauma": "trauma",
        "jaundice_malignancy": "gi",
    }
    return mapping.get(region)


def _extract_candidate_diagnosis(transcript: str) -> str | None:
    text = transcript.strip()
    if not text:
        return None
    patterns = [
        r"(?:working diagnosis|my diagnosis|diagnosis is|i think (?:this )?is|most likely)\s*[:\-–]?\s*([^\.\n;]{4,80})",
        r"(?:impression|ddx|differential)\s*[:\-–]\s*([^\.\n;]{4,80})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .")
    # Heuristic: last user turn that looks like a diagnosis commitment
    return None


def _diagnosis_tokens(text: str) -> set[str]:
    stop = {"acute", "chronic", "the", "a", "an", "of", "and", "with", "for", "to", "in"}
    return {w for w in re.findall(r"[a-zA-Z]+", text.lower()) if len(w) > 3 and w not in stop}


def _assess_diagnosis(session: ClinicalSession) -> dict[str, Any]:
    transcript = _candidate_transcript(session)
    ideal = session.case["ideal_diagnosis"]
    ideal_l = ideal.lower()
    ideal_tokens = _diagnosis_tokens(ideal)
    stated_explicit = bool(
        re.search(
            r"\b(diagnos|impression|working diagnosis|i think this is|most likely)\b",
            transcript,
            flags=re.IGNORECASE,
        )
    )
    candidate = _extract_candidate_diagnosis(transcript)
    # Also treat strong keyword overlap with ideal as stated
    token_hits = sum(1 for t in ideal_tokens if t in transcript.lower())
    keyword_match = token_hits >= max(1, len(ideal_tokens) // 2) and len(ideal_tokens) > 0

    if not stated_explicit and not keyword_match and not candidate:
        proximity = "none"
        questions_to_correct = max(
            3, 6 - sum(1 for m in session.messages if m.role == "user")
        )
        return {
            "diagnosis_stated": False,
            "candidate_diagnosis": None,
            "diagnosis_proximity": proximity,
            "questions_to_correct": questions_to_correct,
            "diagnosis_score_cap": 15,
            "overall_cap": 45,
            "exact": False,
        }

    cand_text = (candidate or transcript).lower()
    if ideal_l in cand_text or all(t in cand_text for t in list(ideal_tokens)[:2]):
        return {
            "diagnosis_stated": True,
            "candidate_diagnosis": candidate or ideal,
            "diagnosis_proximity": "exact",
            "questions_to_correct": 0,
            "diagnosis_score_cap": 100,
            "overall_cap": 100,
            "exact": True,
        }

    # Near-miss / region / system distance
    ideal_region = _region_for_diagnosis(ideal)
    cand_region = _region_for_diagnosis(cand_text if candidate else transcript)
    ideal_sys = _system_for_region(ideal_region)
    cand_sys = _system_for_region(cand_region)

    # Shared stem tokens beyond stopwords
    shared = len(ideal_tokens & _diagnosis_tokens(cand_text))
    user_turns = sum(1 for m in session.messages if m.role == "user")
    feature_hits = sum(
        1
        for f in session.case.get("key_features") or []
        if any(t in transcript.lower() for t in f.lower().split()[:2])
    )
    missing_features = max(0, len(session.case.get("key_features") or []) - feature_hits)
    questions_to_correct = max(1, missing_features + (0 if cand_region == ideal_region else 2))

    if ideal_region and cand_region and ideal_region == cand_region:
        # same anatomical region → near miss (related differential) unless totally empty cand
        if candidate or shared >= 1 or keyword_match:
            proximity, d_cap, o_cap = "near_miss", 75, 75
        else:
            proximity, d_cap, o_cap = "same_region", 55, 65
    elif ideal_sys and cand_sys and ideal_sys == cand_sys:
        proximity, d_cap, o_cap = "same_system", 40, 55
    elif stated_explicit or candidate:
        proximity, d_cap, o_cap = "distant", 20, 45
    else:
        # asked around the topic but never committed
        proximity, d_cap, o_cap = "none", 15, 45
        questions_to_correct = max(questions_to_correct, 4)

    # Incomplete work-up increases distance-to-correct
    if user_turns < 3:
        questions_to_correct = max(questions_to_correct, 4)
        o_cap = min(o_cap, 55)

    return {
        "diagnosis_stated": bool(stated_explicit or candidate or keyword_match),
        "candidate_diagnosis": candidate,
        "diagnosis_proximity": proximity,
        "questions_to_correct": int(questions_to_correct),
        "diagnosis_score_cap": d_cap,
        "overall_cap": o_cap,
        "exact": False,
    }


def _enforce_diagnosis_rubric(parsed: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    subs = dict(parsed.get("subscores") or {})
    for key in ("history_taking", "clinical_reasoning", "diagnosis", "management", "communication"):
        try:
            subs[key] = int(subs.get(key, 0))
        except (TypeError, ValueError):
            subs[key] = 0

    d_cap = int(assessment["diagnosis_score_cap"])
    o_cap = int(assessment["overall_cap"])
    qtc = int(assessment["questions_to_correct"])

    subs["diagnosis"] = min(subs["diagnosis"], d_cap)
    if assessment["diagnosis_proximity"] == "none":
        subs["diagnosis"] = min(subs["diagnosis"], 15)
        subs["management"] = min(subs["management"], 50)
        parsed["pass_likely"] = False
    elif not assessment["exact"]:
        # Wrong diagnosis: management without correct label is capped
        subs["management"] = min(subs["management"], 70 if assessment["diagnosis_proximity"] == "near_miss" else 55)

    if qtc >= 4 and not assessment["exact"]:
        subs["clinical_reasoning"] = max(0, min(subs["clinical_reasoning"], subs["clinical_reasoning"] - 15))

    try:
        overall = int(parsed.get("overall_score", 0))
    except (TypeError, ValueError):
        overall = 0
    recomputed = int(round(sum(subs.values()) / 5))
    # Prefer rubric-aware blend: mean of LLM overall and subscore mean, then cap
    overall = int(round((overall + recomputed) / 2))
    overall = min(overall, o_cap)
    if assessment["diagnosis_proximity"] == "none":
        overall = min(overall, 45)
        parsed["pass_likely"] = False
    else:
        parsed["pass_likely"] = bool(parsed.get("pass_likely", overall >= 60)) and overall >= 60

    parsed["overall_score"] = overall
    parsed["subscores"] = subs
    parsed["diagnosis_stated"] = assessment["diagnosis_stated"]
    parsed["candidate_diagnosis"] = assessment.get("candidate_diagnosis") or parsed.get("candidate_diagnosis")
    parsed["diagnosis_proximity"] = assessment["diagnosis_proximity"]
    parsed["questions_to_correct"] = qtc

    gaps = list(parsed.get("gaps") or [])
    if assessment["diagnosis_proximity"] == "none":
        gaps.insert(0, "No working diagnosis was stated — CST stations require an explicit diagnosis.")
    elif not assessment["exact"]:
        gaps.insert(
            0,
            f"Diagnosis proximity: {assessment['diagnosis_proximity']} "
            f"(~{qtc} focused question(s) from the correct answer).",
        )
    parsed["gaps"] = gaps
    return parsed


def _demo_score(session: ClinicalSession) -> dict[str, Any]:
    assessment = _assess_diagnosis(session)
    transcript = _candidate_transcript(session).lower()
    user_turns = sum(1 for m in session.messages if m.role == "user")
    feature_hits = sum(
        1
        for f in session.case["key_features"]
        if any(t in transcript for t in f.lower().split()[:2])
    )

    if assessment["exact"]:
        diagnosis_score = min(100, 85 + feature_hits * 3)
    elif assessment["diagnosis_proximity"] == "none":
        diagnosis_score = min(15, 5 + feature_hits * 3)
    else:
        floor = {
            "near_miss": 55,
            "same_region": 35,
            "same_system": 25,
            "distant": 10,
        }.get(assessment["diagnosis_proximity"], 10)
        diagnosis_score = min(
            assessment["diagnosis_score_cap"],
            max(floor, floor + feature_hits * 5 - assessment["questions_to_correct"] * 3),
        )

    history_score = min(100, 35 + user_turns * 10)
    reasoning = min(100, 40 + feature_hits * 12 - (0 if assessment["exact"] else assessment["questions_to_correct"] * 5))
    reasoning = max(0, reasoning)
    management = 70 if assessment["exact"] else (45 if assessment["diagnosis_stated"] else 30)
    communication = min(100, 50 + user_turns * 6)
    overall = int(
        round((diagnosis_score + history_score + reasoning + management + communication) / 5)
    )
    overall = min(overall, int(assessment["overall_cap"]))
    if assessment["diagnosis_proximity"] == "none":
        overall = min(overall, 45)

    return _enforce_diagnosis_rubric(
        {
            "overall_score": overall,
            "subscores": {
                "history_taking": history_score,
                "clinical_reasoning": reasoning,
                "diagnosis": diagnosis_score,
                "management": management,
                "communication": communication,
            },
            "what_went_well": [
                "Engaged with the station and asked focused questions",
                "Used the interactive question cards / free-text history",
            ],
            "gaps": [
                f"Ensure you explicitly state: {session.case['ideal_diagnosis']}",
                "Cover key features: " + "; ".join(session.case["key_features"]),
                "State immediate management (resuscitation, investigations, escalation)",
            ],
            "better_answers": [
                {
                    "topic": "Working diagnosis",
                    "candidate_said": assessment.get("candidate_diagnosis") or "Not clearly stated",
                    "stronger_answer": session.case["ideal_diagnosis"],
                    "why": "CST stations reward a clear primary diagnosis with supporting features.",
                },
                {
                    "topic": "Key clinical features",
                    "candidate_said": "Variable",
                    "stronger_answer": "; ".join(session.case["key_features"]),
                    "why": "Link each feature to the diagnosis and next step.",
                },
            ],
            "ideal_summary": (
                f"{session.case['ideal_diagnosis']}. Key points: "
                + "; ".join(session.case["key_features"])
                + ". Resuscitate, investigate appropriately, and escalate for definitive care."
            ),
            "ideal_diagnosis": session.case["ideal_diagnosis"],
            "model_conversation": _model_conversation_for_case(session.case),
            "pass_likely": overall >= 60 and assessment["exact"],
            "demo": True,
            "scoring_model": "heuristic-fallback",
        },
        assessment,
    )


def _finalize_score(parsed: dict[str, Any], session: ClinicalSession, session_id: str) -> dict[str, Any]:
    assessment = _assess_diagnosis(session)
    parsed = _enforce_diagnosis_rubric(parsed, assessment)
    parsed["ideal_diagnosis"] = session.case["ideal_diagnosis"]
    conv = parsed.get("model_conversation")
    if not isinstance(conv, list) or len(conv) < 4:
        parsed["model_conversation"] = _model_conversation_for_case(session.case)
    else:
        cleaned = []
        for turn in conv:
            if isinstance(turn, dict) and turn.get("content"):
                cleaned.append(
                    {
                        "role": "user" if turn.get("role") == "user" else "assistant",
                        "content": str(turn["content"]),
                    }
                )
        parsed["model_conversation"] = cleaned or _model_conversation_for_case(session.case)

    parsed["case"] = {
        "id": session.case["id"],
        "title": session.case["title"],
        "ideal_diagnosis": session.case["ideal_diagnosis"],
        "key_features": session.case["key_features"],
    }
    parsed["session_id"] = session_id
    parsed["scoring_backend"] = parsed.get("scoring_backend") or parsed.get("scoring_model") or "hf-llm"
    return parsed


def score_session(session_id: str, final_answer: str | None = None) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        raise KeyError("Session not found")

    if final_answer:
        session.messages.append(ChatMessage(role="user", content=final_answer))

    if get_settings().use_demo:
        return _finalize_score(_demo_score(session), session, session_id)

    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in session.messages)
    assessment = _assess_diagnosis(session)
    case_blob = json.dumps(
        {
            "title": session.case["title"],
            "stem": session.case["stem"],
            "ideal_diagnosis": session.case["ideal_diagnosis"],
            "key_features": session.case["key_features"],
        }
    )

    llm_messages = [
        {"role": "system", "content": SCORE_PROMPT},
        {
            "role": "user",
            "content": (
                f"CASE:\n{case_blob}\n\nTRANSCRIPT:\n{transcript}\n\n"
                f"Pre-check (apply rubric; you may refine but do not ignore caps):\n"
                f"- diagnosis_stated_heuristic={assessment['diagnosis_stated']}\n"
                f"- candidate_diagnosis_heuristic={assessment.get('candidate_diagnosis')}\n"
                f"- proximity_heuristic={assessment['diagnosis_proximity']}\n"
                f"- questions_to_correct_heuristic={assessment['questions_to_correct']}\n\n"
                "Score this CST station attempt with the diagnosis rubric."
            ),
        },
    ]
    try:
        from app.services.hf_client import hf_service

        raw = hf_service.score_chat(llm_messages, preferred_model=session.hf_model)
        parsed = extract_json_block(raw)
        if parsed:
            parsed["scoring_backend"] = "hf-llm"
            parsed["scoring_model"] = "free-hf-scoring-chain"
    except RuntimeError:
        parsed = None
        raw = ""

    if not parsed:
        parsed = _demo_score(session)
        if raw:
            parsed["raw_feedback"] = raw
    return _finalize_score(parsed, session, session_id)
