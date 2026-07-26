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

## GitHub Pages (frontend) + free cloud backend

Frontend (static): **https://rsteaburdea.github.io/medical-ai/**

Backend must be hosted in the cloud (not on your laptop). Free options for **FastAPI + Hugging Face**:

| Host | Notes |
|------|--------|
| **[Render](https://render.com)** (recommended) | Free web service from `render.yaml` / Docker |
| **Railway** | Free trial credits, then paid |
| **Fly.io** | Free allowance with card sometimes required |
| **Hugging Face Spaces** (Docker) | Needs a HF token with **write** scope |

### Deploy backend on Render (free)

1. Click: **[Deploy to Render](https://render.com/deploy?repo=https://github.com/rsteaburdea/medical-ai)**
2. When prompted, paste your `HF_TOKEN` (Hugging Face → Settings → Access Tokens).
3. Wait until the service is live, copy the URL  
   (example: `https://medical-ai-api.onrender.com`).
4. GitHub repo → **Settings → Secrets and variables → Actions** → secret:
   - Name: `VITE_API_URL`
   - Value: that Render URL (**no** trailing slash)
5. GitHub → **Actions → Deploy GitHub Pages → Run workflow**.

After that, the Pages site talks to Render; your Mac does not need to run the API.

### Connect GitHub Pages → local backend (tunnel)

1. Run backend locally on `:8000`.
2. Expose it with a tunnel (e.g. localhost.run) to get an `https://….lhr.life` URL.
3. Put that URL in `frontend/public/config.json`:

```json
{ "apiUrl": "https://YOUR-TUNNEL.lhr.life" }
```

4. Commit & push (or set GitHub secret `VITE_API_URL` to the same URL and re-run **Deploy GitHub Pages**).

The Pages site reads `config.json` at runtime. Keep the tunnel + local backend running while you use the site.

## Disclaimer

Educational simulation only — not clinical advice, not a substitute for real CST assessment.
