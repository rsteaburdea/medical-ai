from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    return " ".join(text.lower().split()).rstrip("?.!")


def _sex_pronouns(stem: str) -> tuple[str, str, str]:
    s = stem.lower()
    if re.search(r"\b(female|woman|girl|she|her)\b", s):
        return "She", "she", "her"
    if re.search(r"\b(male|man|boy|he|his)\b", s):
        return "He", "he", "his"
    return "They", "they", "their"


def _dx_l(case: dict[str, Any]) -> str:
    return str(case.get("ideal_diagnosis") or "").lower()


def _features_blob(case: dict[str, Any]) -> str:
    return " ".join(str(f) for f in (case.get("key_features") or [])).lower()


def _answer_templates(case: dict[str, Any]) -> list[tuple[tuple[str, ...], str]]:
    """Keyword groups → realistic examiner/patient answers for this case."""
    He, he, his = _sex_pronouns(case.get("stem") or "")
    dx = _dx_l(case)
    feat = _features_blob(case)
    stem = (case.get("stem") or "").lower()

    # Shared defaults
    rows: list[tuple[tuple[str, ...], str]] = [
        (
            ("vomit", "vomiting", "emesis"),
            f"{He} has vomited a few times — small volume. No haematemesis."
            if "bleed" not in dx and "haemat" not in feat
            else f"{He} has had several episodes of vomiting with dark material; volume is hard to quantify.",
        ),
        (
            ("flatus", "wind", "pass gas"),
            f"{He} has not passed flatus since symptoms began."
            if "obstruction" in dx or "ileus" in dx or "constipat" in stem
            else f"{He} is still passing flatus.",
        ),
        (
            ("urin", "dysuria", "frequency", "haematuria"),
            f"No dysuria, frequency, or haematuria. Last void was normal.",
        ),
        (
            ("diarr", "bowel", "stool", "pr bleed", "melaena", "melena", "rectal"),
            f"{He} reports dark / bloody stool and feels light-headed."
            if any(k in dx or k in feat for k in ("bleed", "diverticul", "melaena", "gi bleed"))
            else f"No diarrhoea or PR bleeding. Bowels opened as usual yesterday.",
        ),
        (
            ("blood loss", "volume", "how much blood", "clots"),
            f"{He} estimates several large episodes of bright red blood per rectum; "
            f"pads/toilet bowl filled more than once. Exact volume uncertain — treat as significant until proven otherwise."
            if "bleed" in dx or "bleed" in feat or "diverticul" in dx
            else f"No major external bleeding reported.",
        ),
        (
            ("syncope", "faint", "collapse", "dizzy", "light-head"),
            f"{He} had near-syncope on standing and feels dizzy."
            if any(k in stem or k in feat for k in ("tachycard", "hypotens", "shock", "bleed", "hr 1", "bp 9", "bp 8"))
            or "bleed" in dx
            else f"No syncope. Mild light-headedness only if present at all.",
        ),
        (
            ("previous", "past history", "pmh", "prior episode", "diverticular", "operations", "surgery", "surg"),
            f"Past history includes relevant prior episodes consistent with the presentation; "
            f"no other major laparotomies beyond what is already in the stem."
            if "diverticul" in dx or "adhes" in dx or "surg" in stem
            else f"No major previous abdominal surgery. Past history otherwise unremarkable beyond the stem.",
        ),
        (
            ("fever", "rigor", "temperature"),
            f"There has been low-grade fever / feeling hot."
            if any(k in stem for k in ("37.", "38.", "fever"))
            else f"No frank rigors. Temperature as in the stem.",
        ),
        (
            ("anorex", "appetite", "eat", "last meal", "oral intake", "npo", "fluids"),
            f"{He} has lost {his} appetite and last took clear fluids several hours ago.",
        ),
        (
            ("pain becoming", "constant", "colick"),
            f"Pain was colicky; it is becoming more constant and severe."
            if "obstruction" in dx or "ischaem" in dx
            else f"Pain remains as described in the stem — progressive rather than settling.",
        ),
        (
            ("hernia",),
            f"No obvious groin or incisional hernia on inspection so far."
            if "hernia" not in dx
            else f"There is a tender, irreducible groin swelling — skin changes may be present.",
        ),
        (
            ("nature of the vomit", "bilious", "faeculant"),
            f"Vomiting is bilious."
            if "obstruction" in dx or "bilious" in stem
            else f"Vomiting is small-volume and non-bilious.",
        ),
        (
            ("exam", "abdomen", "tender", "guard", "periton", "rebound", "scrot", "pulse", "leg", "breast"),
            _exam_answer(case, He, he, his),
        ),
        (
            ("blood", "wcc", "crp", "investigat", "lactate", "fbc", "u&e", "imaging", "ct", "ultrasound", "x-ray"),
            _ix_answer(case),
        ),
        (
            ("resuscit", "iv access", "abc", "risk strat", "haemodynamic"),
            "Vitals are as in the stem. Please state your working diagnosis and immediate management; "
            "I will not coach the next clinical steps during the viva.",
        ),
        (
            ("working diagnosis", "my diagnosis", "management", "plan"),
            "Noted. I will not confirm the diagnosis yet — please commit clearly, then use End & score.",
        ),
    ]
    return rows


def _exam_answer(case: dict[str, Any], He: str, he: str, his: str) -> str:
    dx = _dx_l(case)
    if "appendic" in dx:
        return "Tender at McBurney's point with rebound. Rovsing may be positive. No generalised peritonism. Genitalia normal."
    if "obstruction" in dx or "sbo" in dx:
        return "Distended, tympanic abdomen with tinkling bowel sounds. Mild diffuse tenderness; watch for peritonism."
    if "cholecyst" in dx:
        return "Tender in the right upper quadrant with a positive Murphy's sign. No generalised peritonism."
    if "torsion" in dx:
        return "Exquisitely tender high-riding testis; cremasteric reflex absent on the affected side."
    if "ischaem" in dx or "ischemia" in dx:
        return "Affected limb is pale/pulseless/painful with sensory change — compare with the other side."
    if "bleed" in dx or "diverticul" in dx:
        return "Abdomen soft, not peritonitic. PR: fresh blood. Patient looks pale; capillary refill may be prolonged."
    if "perforat" in dx or "ulcer" in dx:
        return "Board-like rigidity with generalised peritonism. Silent abdomen."
    if "aaa" in dx or "aortic" in dx:
        return "Expansile pulsatile mass if palpable; patient may be shocked. Femoral pulses — compare sides."
    if "pancreat" in dx:
        return "Epigastric tenderness; may have guarding. Cullen/Grey-Turner usually absent early."
    if "hernia" in dx:
        return "Tender irreducible hernia at the relevant orifice; assess overlying skin."
    feat = case.get("key_features") or []
    return (
        f"Examination supports the key findings for this presentation"
        + (f": {'; '.join(feat[:2])}" if feat else "")
        + f". Vitals remain as in the stem."
    )


def _ix_answer(case: dict[str, Any]) -> str:
    dx = _dx_l(case)
    if "appendic" in dx:
        return "WCC raised, CRP elevated, U&E normal. Pregnancy test N/A / negative if relevant. Imaging not mandatory if clinical diagnosis is clear."
    if "obstruction" in dx:
        return "AXR/CT shows dilated small bowel with transition point; lactate — check for ischaemia. U&E may show dehydration."
    if "cholecyst" in dx:
        return "WCC/CRP up; LFTs may be mildly deranged. Ultrasound: thick-walled gallbladder ± stones, sonographic Murphy positive."
    if "bleed" in dx or "diverticul" in dx:
        return "FBC shows anaemia / falling Hb if rechecked; U&E, coagulation, group & save/crossmatch. Lactate if shocked."
    if "pancreat" in dx:
        return "Lipase/amylase markedly elevated; FBC, U&E, LFTs, glucose, calcium. Consider ultrasound for gallstones."
    if "torsion" in dx:
        return "Do not delay for imaging if clinical suspicion is high. Doppler USS only if it will not delay theatre."
    return "Basic bloods return results compatible with an acute surgical presentation; choose imaging appropriate to your differential."


def build_answer_bank(case: dict[str, Any]) -> dict[str, str]:
    """Map normalised suggested (and related) questions → instant answers."""
    bank: dict[str, str] = {}
    templates = _answer_templates(case)

    questions = list(case.get("suggested_questions") or [])
    questions.extend(
        [
            "May I examine the relevant system now?",
            "May I examine the abdomen?",
            "Any fever or rigors?",
            "What are the current vital signs?",
            "I would like bloods: FBC, CRP, U&E (and β-hCG if relevant).",
            "What imaging is most appropriate next?",
            "Any red-flag symptoms I should ask about?",
            "When did this start and how has it progressed?",
            "Confirm the volume of blood loss.",
            "Any syncope or light-headedness?",
            "Previous diverticular disease?",
        ]
    )

    for q in questions:
        n = _norm(q)
        if not n or n in bank:
            continue
        bank[n] = _match_template(q, templates) or _generic_from_stem(case, q)

    return bank


def _match_template(question: str, templates: list[tuple[tuple[str, ...], str]]) -> str | None:
    q = question.lower()
    for keys, answer in templates:
        if any(k in q for k in keys):
            return answer
    return None


def _generic_from_stem(case: dict[str, Any], question: str) -> str:
    He, he, his = _sex_pronouns(case.get("stem") or "")
    feats = case.get("key_features") or []
    tip = feats[0] if feats else "the findings already summarised in the stem"
    return (
        f"{He} answers in keeping with the stem. Regarding your question — "
        f"the most relevant point so far is: {tip}. Please continue your focused history or examination."
    )


def instant_answer(case: dict[str, Any], user_message: str, bank: dict[str, str] | None = None) -> str | None:
    """Return a cached/predefined answer if this looks like a known card or template hit."""
    bank = bank if bank is not None else build_answer_bank(case)
    n = _norm(user_message)
    if n in bank:
        return bank[n]

    # Fuzzy: high token overlap with a bank key
    q_tokens = set(n.split())
    best: tuple[float, str] | None = None
    for key, ans in bank.items():
        k_tokens = set(key.split())
        if not k_tokens:
            continue
        overlap = len(q_tokens & k_tokens) / max(len(k_tokens), 1)
        if overlap >= 0.72 and (best is None or overlap > best[0]):
            best = (overlap, ans)
    if best:
        return best[1]

    # Template keyword fallback for free-text that still matches clinical patterns
    return _match_template(user_message, _answer_templates(case))
