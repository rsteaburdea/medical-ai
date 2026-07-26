from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AgentCategory = Literal["clinical", "pubmed_match", "pubmed_chat"]


class ModelInfo(BaseModel):
    id: str
    name: str
    huggingface_id: str
    description: str
    size: str
    strengths: list[str]
    training_datasets: list[str] = Field(default_factory=list)
    multimodal: bool = False
    recommended: bool = False


class AgentInfo(BaseModel):
    id: str
    category: AgentCategory
    name: str
    tagline: str
    description: str
    models: list[ModelInfo]
    default_model: str


CLINICAL_MODELS = [
    ModelInfo(
        id="med42-8b",
        name="Med42-v2 8B",
        huggingface_id="m42-health/Llama3-Med42-8B:featherless-ai",
        description=(
            "Clinically aligned Llama 3 model (M42 Health). Served via Hugging Face Inference "
            "Providers (featherless-ai). Best fit for CST diagnostic viva."
        ),
        size="8B",
        strengths=["Clinical Q&A", "Diagnostic reasoning", "HF provider (featherless)"],
        training_datasets=[
            "Llama 3 base pretraining mixture",
            "Medical instruction / preference tuning (Med42-v2 / M42 Health)",
            "Clinical QA-style alignment data",
        ],
        recommended=True,
    ),
    ModelInfo(
        id="llama33-70b",
        name="Llama 3.3 70B Instruct",
        huggingface_id="meta-llama/Llama-3.3-70B-Instruct",
        description=(
            "Strong general instruct model on free HF Inference. Reliable CST examiner / scorer "
            "when Med42 is unavailable or slow."
        ),
        size="70B",
        strengths=["Free serverless", "Structured JSON", "Long context"],
        training_datasets=[
            "Llama 3 pretraining mixture",
            "Instruction SFT + preference tuning (Meta)",
        ],
    ),
    ModelInfo(
        id="qwen25-72b",
        name="Qwen2.5 72B Instruct",
        huggingface_id="Qwen/Qwen2.5-72B-Instruct",
        description=(
            "Large free instruct model — good fallback for viva replies, summarisation, and scoring."
        ),
        size="72B",
        strengths=["Free serverless", "Multilingual", "Instruction following"],
        training_datasets=[
            "Large multilingual web / books / code",
            "Instruction SFT + preference tuning (Qwen)",
        ],
    ),
    ModelInfo(
        id="llama31-8b",
        name="Llama 3.1 8B Instruct",
        huggingface_id="meta-llama/Llama-3.1-8B-Instruct",
        description=(
            "Smaller free instruct model — faster / lighter fallback when larger models are busy."
        ),
        size="8B",
        strengths=["Free serverless", "Low latency", "Lightweight"],
        training_datasets=[
            "Llama 3.1 pretraining mixture",
            "Instruction SFT + preference tuning (Meta)",
        ],
    ),
]

PUBMED_MATCH_MODELS = [
    ModelInfo(
        id="pubmedbert-embeddings",
        name="PubMedBERT Embeddings",
        huggingface_id="NeuML/pubmedbert-base-embeddings",
        description=(
            "PubMed title–abstract embeddings via HF Inference (sentence_similarity). "
            "Best free option for matching pasted text to articles."
        ),
        size="110M",
        strengths=["Semantic search", "Article matching", "hf-inference provider"],
        training_datasets=[
            "PubMed abstracts (PubMedBERT / BiomedBERT lineage)",
            "Title–abstract pairs for embedding contrastive training (NeuML)",
        ],
        recommended=True,
    ),
    ModelInfo(
        id="spubmedbert-msmarco",
        name="S-PubMedBERT MS-MARCO",
        huggingface_id="pritamdeka/S-PubMedBert-MS-MARCO",
        description=(
            "Sentence-transformers PubMedBERT fine-tuned on MS-MARCO — solid free biomedical "
            "retrieval fallback."
        ),
        size="110M",
        strengths=["Biomedical retrieval", "Sentence embeddings", "Free Inference"],
        training_datasets=[
            "PubMedBERT / BiomedBERT base",
            "MS-MARCO passage ranking pairs",
        ],
    ),
    ModelInfo(
        id="sapbert-pubmed",
        name="SapBERT (PubMedBERT)",
        huggingface_id="cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
        description=(
            "Entity-oriented biomedical embeddings (UMLS / SapBERT). Better for short concept "
            "phrases than long paragraphs — useful fallback for keyword-like snippets."
        ),
        size="110M",
        strengths=["Medical entities", "Concept matching", "Free Inference"],
        training_datasets=[
            "PubMedBERT fulltext",
            "UMLS synonym pairs (self-alignment)",
        ],
    ),
    ModelInfo(
        id="minilm-l6",
        name="MiniLM L6 v2",
        huggingface_id="sentence-transformers/all-MiniLM-L6-v2",
        description=(
            "General-purpose free sentence embedding model — lighter / faster fallback when "
            "biomedical embedding endpoints are busy."
        ),
        size="22M",
        strengths=["Free serverless", "Fast", "General semantic search"],
        training_datasets=[
            "Large sentence-pair corpora (sentence-transformers)",
        ],
    ),
]

PUBMED_CHAT_MODELS = [
    ModelInfo(
        id="pmc-llama-summ",
        name="PMC-LLaMA PubMedSumm",
        huggingface_id="clinicalnlplab/finetuned-PMCLLaMA-PubmedSumm",
        description=(
            "Fine-tuned for PubMed / PMC summarisation. Served via featherless-ai text generation — "
            "best available free biomedical summariser for literature chat."
        ),
        size="~7B",
        strengths=["PubMed summarisation", "Biomedical literature", "featherless-ai"],
        training_datasets=[
            "PMC / PubMed literature",
            "PubMed summarisation fine-tune (clinicalnlplab)",
        ],
        recommended=True,
    ),
    ModelInfo(
        id="qwen25-72b-lit",
        name="Qwen2.5 72B Instruct",
        huggingface_id="Qwen/Qwen2.5-72B-Instruct",
        description=(
            "General free instruct model — strong literature chat / comparison when PMC-LLaMA is down."
        ),
        size="72B",
        strengths=["Free serverless", "Summaries", "Literature synthesis"],
        training_datasets=[
            "Large multilingual web text",
            "Code & math corpora",
            "Instruction SFT + preference tuning (Qwen)",
        ],
    ),
    ModelInfo(
        id="llama33-70b-lit",
        name="Llama 3.3 70B Instruct",
        huggingface_id="meta-llama/Llama-3.3-70B-Instruct",
        description=(
            "Free HF Inference fallback for PubMed chat — reliable when specialised models fail."
        ),
        size="70B",
        strengths=["Free serverless", "Chat", "Structured answers"],
        training_datasets=[
            "Llama 3 pretraining mixture",
            "Instruction SFT + preference tuning (Meta)",
        ],
    ),
]

AGENTS: list[AgentInfo] = [
    AgentInfo(
        id="clinical-station",
        category="clinical",
        name="Clinical Case Station",
        tagline="Core Surgical Training viva simulator (Ireland)",
        description=(
            "Simulates an RCSI-style clinical case station. An interviewer presents a patient case; "
            "you take a focused history via follow-up question cards, commit to a diagnosis and plan, "
            "then receive a structured score with better-answer coaching."
        ),
        models=CLINICAL_MODELS,
        default_model="med42-8b",
    ),
    AgentInfo(
        id="pubmed-matcher",
        category="pubmed_match",
        name="PubMed Article Matcher",
        tagline="Identify which papers a text fragment belongs to",
        description=(
            "Embeds your pasted text and ranks the top matching PubMed articles from the curated corpus "
            "using cosine similarity. When confidence is high, returns the exact article."
        ),
        models=PUBMED_MATCH_MODELS,
        default_model="pubmedbert-embeddings",
    ),
    AgentInfo(
        id="pubmed-chat",
        category="pubmed_chat",
        name="PubMed Literature Chat",
        tagline="Search, summarise, and discuss biomedical papers",
        description=(
            "Conversational agent for PubMed: find papers on a topic, summarise abstracts, "
            "compare findings, or draft new content grounded in literature."
        ),
        models=PUBMED_CHAT_MODELS,
        default_model="pmc-llama-summ",
    ),
]


def get_agent(agent_id: str) -> AgentInfo | None:
    return next((a for a in AGENTS if a.id == agent_id), None)


def get_model(agent_id: str, model_id: str) -> ModelInfo | None:
    agent = get_agent(agent_id)
    if not agent:
        return None
    return next((m for m in agent.models if m.id == model_id), None)


def resolve_hf_id(agent_id: str, model_id: str) -> str | None:
    model = get_model(agent_id, model_id)
    return model.huggingface_id if model else None
