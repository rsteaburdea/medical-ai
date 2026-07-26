from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_settings

logger = logging.getLogger(__name__)

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "pubmed_corpus.json"

# sentence_similarity scores are typically lower than cosine of L2-normalized vectors
SIMILARITY_EXACT_THRESHOLD = 0.55
EMBED_EXACT_THRESHOLD = 0.86
TFIDF_EXACT_THRESHOLD = 0.55
TOP_K = 3


@lru_cache
def load_corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _article_text(article: dict[str, Any]) -> str:
    return f"{article['title']}. {article['abstract']}"


class PubMedMatcher:
    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None
        self._model: str | None = None
        self._backend: str = "none"
        self._tfidf: TfidfVectorizer | None = None
        self._texts: list[str] | None = None

    def _corpus_texts(self) -> list[str]:
        if self._texts is None:
            self._texts = [_article_text(a) for a in load_corpus()]
        return self._texts

    def _ensure_embed_index(self, model: str) -> None:
        if self._matrix is not None and self._model == model and self._backend == "hf-embed":
            return
        from app.services.hf_client import hf_service

        texts = self._corpus_texts()
        logger.info("Building PubMed embedding index (%d articles) with %s", len(texts), model)
        vectors = hf_service.embed(texts, model=model)
        matrix = np.array(vectors, dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = matrix / norms
        self._backend = "hf-embed"
        self._tfidf = None
        self._model = model

    def _ensure_tfidf(self) -> None:
        if self._backend == "tfidf" and self._tfidf is not None:
            return
        texts = self._corpus_texts()
        self._tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=8000)
        self._matrix = self._tfidf.fit_transform(texts)  # type: ignore[assignment]
        self._backend = "tfidf"
        self._model = "tfidf"

    def match(self, query: str, model: str | None = None, top_k: int = TOP_K) -> dict[str, Any]:
        settings = get_settings()
        emb_model = model or settings.embedding_model
        corpus = load_corpus()
        texts = self._corpus_texts()
        threshold = SIMILARITY_EXACT_THRESHOLD

        try:
            from app.services.hf_client import hf_service

            scores_list = hf_service.sentence_similarity(query, texts, model=emb_model)
            scores = np.array(scores_list, dtype=float)
            self._backend = "hf-similarity"
            self._model = emb_model
        except Exception as sim_err:
            logger.warning("sentence_similarity unavailable (%s) — trying embeddings", sim_err)
            try:
                self._ensure_embed_index(emb_model)
                assert self._matrix is not None
                from app.services.hf_client import hf_service

                q_vec = np.array(hf_service.embed([query], model=emb_model)[0], dtype=float).reshape(1, -1)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_vec = q_vec / q_norm
                scores = cosine_similarity(q_vec, self._matrix)[0]
                threshold = EMBED_EXACT_THRESHOLD
            except Exception as emb_err:
                logger.warning("HF embeddings unavailable (%s) — using TF-IDF fallback", emb_err)
                self._ensure_tfidf()
                assert self._tfidf is not None and self._matrix is not None
                q_vec = self._tfidf.transform([query])
                scores = cosine_similarity(q_vec, self._matrix)[0]
                threshold = TFIDF_EXACT_THRESHOLD

        order = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in order:
            article = corpus[int(idx)]
            score = float(scores[int(idx)])
            results.append(
                {
                    "pmid": article["pmid"],
                    "title": article["title"],
                    "abstract": article["abstract"],
                    "journal": article.get("journal"),
                    "year": article.get("year"),
                    "topics": article.get("topics", []),
                    "score": round(score, 4),
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
                }
            )

        best = results[0] if results else None
        exact = best is not None and best["score"] >= threshold
        model_label = emb_model if self._backend.startswith("hf") else f"{emb_model} (tfidf-fallback)"

        return {
            "query": query,
            "model": model_label,
            "exact_match": exact,
            "exact_article": best if exact else None,
            "top_matches": results,
            "threshold": threshold,
            "corpus_size": len(corpus),
            "backend": self._backend,
        }


pubmed_matcher = PubMedMatcher()
