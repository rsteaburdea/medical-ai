export type AgentCategory = "clinical" | "pubmed_match" | "pubmed_chat";

export interface ModelInfo {
  id: string;
  name: string;
  huggingface_id: string;
  description: string;
  size: string;
  strengths: string[];
  training_datasets?: string[];
  multimodal?: boolean;
  recommended?: boolean;
}

export interface AgentInfo {
  id: string;
  category: AgentCategory;
  name: string;
  tagline: string;
  description: string;
  models: ModelInfo[];
  default_model: string;
}

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ClinicalSession {
  session_id: string;
  model_id: string;
  case: { id: string; title: string; stem: string };
  messages: ChatMessage[];
  suggested_questions: string[];
  phase: string;
}

export interface ScoreResult {
  overall_score: number;
  subscores: Record<string, number>;
  what_went_well: string[];
  gaps: string[];
  better_answers: Array<{
    topic: string;
    candidate_said: string;
    stronger_answer: string;
    why: string;
  }>;
  ideal_summary: string;
  ideal_diagnosis?: string;
  candidate_diagnosis?: string | null;
  diagnosis_stated?: boolean;
  diagnosis_proximity?: string;
  questions_to_correct?: number;
  model_conversation?: ChatMessage[];
  pass_likely: boolean;
  scoring_backend?: string;
  case?: {
    id: string;
    title: string;
    ideal_diagnosis: string;
    key_features: string[];
  };
}

export interface MatchResult {
  query: string;
  model: string;
  exact_match: boolean;
  exact_article: MatchArticle | null;
  top_matches: MatchArticle[];
  threshold: number;
  corpus_size: number;
}

export interface MatchArticle {
  pmid: string;
  title: string;
  abstract: string;
  journal?: string;
  year?: number | string;
  topics?: string[];
  score: number;
  pubmed_url: string;
}

export interface PubMedChatSession {
  session_id: string;
  model_id: string;
  messages: ChatMessage[];
  last_articles: MatchArticle[];
}

const SERVER_UNAVAILABLE =
  "Server not available. Models and agents will appear when the backend is back online.";

export { SERVER_UNAVAILABLE };

let apiBaseResolved: string | null = null;
let apiBasePromise: Promise<string> | null = null;

async function resolveApiBase(): Promise<string> {
  if (apiBaseResolved != null) return apiBaseResolved;
  if (!apiBasePromise) {
    apiBasePromise = (async () => {
      // Prefer runtime config.json so GitHub Pages can retarget the API without a stale
      // VITE_API_URL secret baked into the JS bundle.
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}config.json`, { cache: "no-store" });
        if (res.ok) {
          const cfg = (await res.json()) as { apiUrl?: string };
          const url = (cfg.apiUrl ?? "").replace(/\/$/, "");
          if (url) {
            apiBaseResolved = url;
            return url;
          }
        }
      } catch {
        /* ignore — fall through */
      }
      const fromEnv = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
      if (fromEnv) {
        apiBaseResolved = fromEnv;
        return fromEnv;
      }
      apiBaseResolved = "";
      return "";
    })();
  }
  return apiBasePromise;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const API_BASE = await resolveApiBase();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch {
    throw new Error(SERVER_UNAVAILABLE);
  }
  if (!res.ok) {
    if (res.status === 404 || res.status >= 500 || res.status === 0) {
      throw new Error(SERVER_UNAVAILABLE);
    }
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<{ status: string; hf_token_configured: boolean; demo_mode?: boolean }>("/api/health"),
  agents: () => request<{ agents: AgentInfo[] }>("/api/agents"),
  clinicalCases: () =>
    request<{
      cases: Array<{ id: string; title: string; stem: string; generated?: boolean }>;
    }>("/api/clinical/cases"),
  generateClinicalCase: (model_id: string) =>
    request<{ case: { id: string; title: string; stem: string; generated?: boolean } }>(
      "/api/clinical/cases/generate",
      {
        method: "POST",
        body: JSON.stringify({ model_id }),
      },
    ),
  startClinical: (model_id: string, case_id?: string) =>
    request<ClinicalSession>("/api/clinical/start", {
      method: "POST",
      body: JSON.stringify({ model_id, case_id }),
    }),
  clinicalChat: (session_id: string, message: string) =>
    request<ClinicalSession>("/api/clinical/chat", {
      method: "POST",
      body: JSON.stringify({ session_id, message }),
    }),
  clinicalScore: (session_id: string, final_answer?: string) =>
    request<ScoreResult>("/api/clinical/score", {
      method: "POST",
      body: JSON.stringify({ session_id, final_answer }),
    }),
  matchText: (text: string, model_id = "pubmedbert-embeddings") =>
    request<MatchResult>("/api/pubmed/match", {
      method: "POST",
      body: JSON.stringify({ text, model_id }),
    }),
  startPubMedChat: (model_id: string) =>
    request<PubMedChatSession>("/api/pubmed/chat/start", {
      method: "POST",
      body: JSON.stringify({ model_id }),
    }),
  pubmedChat: (session_id: string, message: string, search_query?: string) =>
    request<PubMedChatSession>("/api/pubmed/chat", {
      method: "POST",
      body: JSON.stringify({ session_id, message, search_query }),
    }),
};
