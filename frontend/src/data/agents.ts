import type { AgentInfo } from "../api/client";

/** Static catalog so the UI shows models when GitHub Pages has no backend API. */
export const FALLBACK_AGENTS: AgentInfo[] = [
  {
    id: "clinical-station",
    category: "clinical",
    name: "Clinical Case Station",
    tagline: "Core Surgical Training viva simulator (Ireland)",
    description:
      "Simulates an RCSI-style clinical case station. An interviewer presents a patient case; you take a focused history via follow-up question cards, commit to a diagnosis and plan, then receive a structured score with better-answer coaching.",
    default_model: "med42-8b",
    models: [
      {
        id: "med42-8b",
        name: "Med42-v2 8B",
        huggingface_id: "m42-health/Llama3-Med42-8B:featherless-ai",
        description:
          "Clinically aligned Llama 3 model (M42 Health). Served via Hugging Face Inference Providers (featherless-ai). Best fit for CST diagnostic viva; falls back to Llama 3.3 if unavailable.",
        size: "8B",
        strengths: ["Clinical Q&A", "Diagnostic reasoning", "HF provider (featherless)"],
        training_datasets: [
          "Llama 3 base pretraining mixture",
          "Medical instruction / preference tuning (Med42-v2 / M42 Health)",
          "Clinical QA-style alignment data",
        ],
        recommended: true,
      },
    ],
  },
  {
    id: "pubmed-matcher",
    category: "pubmed_match",
    name: "PubMed Article Matcher",
    tagline: "Identify which papers a text fragment belongs to",
    description:
      "Embeds your pasted text and ranks the top matching PubMed articles from the curated corpus using cosine similarity. When confidence is high, returns the exact article.",
    default_model: "pubmedbert-embeddings",
    models: [
      {
        id: "pubmedbert-embeddings",
        name: "PubMedBERT Embeddings",
        huggingface_id: "NeuML/pubmedbert-base-embeddings",
        description:
          "PubMed title–abstract embeddings via HF Inference (sentence_similarity). Best free option for matching pasted text to articles.",
        size: "110M",
        strengths: ["Semantic search", "Article matching", "hf-inference provider"],
        training_datasets: [
          "PubMed abstracts (PubMedBERT / BiomedBERT lineage)",
          "Title–abstract pairs for embedding contrastive training (NeuML)",
        ],
        recommended: true,
      },
    ],
  },
  {
    id: "pubmed-chat",
    category: "pubmed_chat",
    name: "PubMed Literature Chat",
    tagline: "Search, summarise, and discuss biomedical papers",
    description:
      "Conversational agent for PubMed: find papers on a topic, summarise abstracts, compare findings, or draft new content grounded in literature.",
    default_model: "pmc-llama-summ",
    models: [
      {
        id: "pmc-llama-summ",
        name: "PMC-LLaMA PubMedSumm",
        huggingface_id: "clinicalnlplab/finetuned-PMCLLaMA-PubmedSumm",
        description:
          "Fine-tuned for PubMed / PMC summarisation. Served via featherless-ai text generation — best available free biomedical summariser for literature chat.",
        size: "~7B",
        strengths: ["PubMed summarisation", "Biomedical literature", "featherless-ai"],
        training_datasets: [
          "PMC / PubMed literature",
          "PubMed summarisation fine-tune (clinicalnlplab)",
        ],
        recommended: true,
      },
    ],
  },
];
