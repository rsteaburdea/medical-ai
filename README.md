# MedTrain AI

React + FastAPI app with three Hugging Face–powered agents for surgical training and PubMed workflows. Anyone with the URL can use it once deployed.

Uses **one best available Hugging Face model per agent**:
- Clinical CST: `m42-health/Llama3-Med42-8B:featherless-ai` (fallback Llama 3.3 / Qwen)
- PubMed matcher: `NeuML/pubmedbert-base-embeddings` via `sentence_similarity` (hf-inference)
- Literature chat: `clinicalnlplab/finetuned-PMCLLaMA-PubmedSumm` via featherless-ai

## Agents

1. **Clinical Case Station** — RCSI-style CST viva with question cards, then score + better answers.
2. **PubMed Article Matcher** — paste a fragment → top 3 / exact match via PubMedBERT embeddings.
3. **PubMed Literature Chat** — search live PubMed, summarise, compare, draft.

## Quick start (local)

### 1. Hugging Face token

```bash
cp backend/.env.example backend/.env
```

Set `HF_TOKEN` from https://huggingface.co/settings/tokens (read / inference access).

### 2. Backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Without a real `HF_TOKEN`, clinical station uses a demo examiner and matcher falls back to TF-IDF.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Shareable link (Docker)

```bash
cp backend/.env.example backend/.env   # set HF_TOKEN
docker compose up --build
```

App: **http://localhost:8080**

## Disclaimer

Educational simulation only — not clinical advice, not a substitute for real CST assessment.
