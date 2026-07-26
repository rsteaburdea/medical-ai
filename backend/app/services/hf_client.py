from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from huggingface_hub import InferenceClient

from app.config import get_settings

logger = logging.getLogger(__name__)

MED42_PROVIDER = "m42-health/Llama3-Med42-8B:featherless-ai"
PMC_SUMM = "clinicalnlplab/finetuned-PMCLLaMA-PubmedSumm"
LLAMA33 = "meta-llama/Llama-3.3-70B-Instruct"
QWEN72 = "Qwen/Qwen2.5-72B-Instruct"
LLAMA31 = "meta-llama/Llama-3.1-8B-Instruct"

# Models that work via text_generation (not chat completions)
TEXT_GENERATION_MODELS = {
    PMC_SUMM,
    f"{PMC_SUMM}:featherless-ai",
}

DEFAULT_LIVE_CHAT = MED42_PROVIDER
FALLBACK_CHAIN = [MED42_PROVIDER, LLAMA33, QWEN72, LLAMA31]
# Prefer strong free instruct models for structured CST scoring JSON
SCORING_CHAIN = [LLAMA33, QWEN72, MED42_PROVIDER, LLAMA31]


class HFService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: InferenceClient | None = None
        self._embed_client: InferenceClient | None = None
        self._featherless: InferenceClient | None = None

    @property
    def client(self) -> InferenceClient:
        if self._client is None:
            self._client = InferenceClient(api_key=self.settings.hf_token or None)
        return self._client

    @property
    def embed_client(self) -> InferenceClient:
        if self._embed_client is None:
            self._embed_client = InferenceClient(
                provider="hf-inference",
                api_key=self.settings.hf_token or None,
            )
        return self._embed_client

    @property
    def featherless(self) -> InferenceClient:
        if self._featherless is None:
            self._featherless = InferenceClient(
                provider="featherless-ai",
                api_key=self.settings.hf_token or None,
            )
        return self._featherless

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        fallback_chain: list[str] | None = None,
    ) -> str:
        base = model.split(":")[0]
        if model in TEXT_GENERATION_MODELS or base in TEXT_GENERATION_MODELS:
            try:
                return self._text_generation_chat(base, messages, max_tokens=max_tokens)
            except Exception as err:
                logger.warning("text_generation chat failed for %s: %s", model, err)

        chain: list[str] = []
        for m in [model, *(fallback_chain if fallback_chain is not None else FALLBACK_CHAIN)]:
            if m and m not in chain:
                chain.append(m)

        errors: list[str] = []
        for target in chain:
            try:
                return self._chat_completion(
                    target, messages, max_tokens=max_tokens, temperature=temperature
                )
            except Exception as err:
                msg = str(err).replace("\n", " ")[:180]
                logger.warning("chat failed for %s: %s", target, msg)
                errors.append(f"{target}: {msg}")
                if "503" in msg and "Med42" in target:
                    time.sleep(1.5)
                    try:
                        return self._chat_completion(
                            target, messages, max_tokens=max_tokens, temperature=temperature
                        )
                    except Exception as retry_err:
                        errors.append(f"{target} retry: {str(retry_err).replace(chr(10), ' ')[:120]}")
                        continue

        raise RuntimeError("Hugging Face chat failed for all models. " + " | ".join(errors[:3]))

    def score_chat(
        self,
        messages: list[dict[str, str]],
        *,
        preferred_model: str | None = None,
        max_tokens: int = 1800,
        temperature: float = 0.2,
    ) -> str:
        """Structured scoring via free HF instruct models (Llama 3.3 → Qwen → Med42)."""
        start = preferred_model or SCORING_CHAIN[0]
        return self.chat(
            start,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            fallback_chain=SCORING_CHAIN,
        )

    def _chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.content or ""
        except Exception:
            completion = self.client.chat_completion(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.content or ""

    def _text_generation_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
    ) -> str:
        prompt = self._messages_to_prompt(messages)
        out = self.featherless.text_generation(
            prompt,
            model=model,
            max_new_tokens=max_tokens,
            return_full_text=False,
        )
        return out if isinstance(out, str) else str(out)

    @staticmethod
    def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for m in messages:
            role = m.get("role", "user").upper()
            parts.append(f"{role}: {m.get('content', '')}")
        parts.append("ASSISTANT:")
        return "\n\n".join(parts)

    def sentence_similarity(
        self,
        source: str,
        sentences: list[str],
        model: str | None = None,
    ) -> list[float]:
        emb_model = model or self.settings.embedding_model
        result = self.embed_client.sentence_similarity(
            source,
            other_sentences=sentences,
            model=emb_model,
        )
        return [float(x) for x in result]

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        emb_model = model or self.settings.embedding_model
        vectors: list[list[float]] = []
        for text in texts:
            try:
                result = self.embed_client.feature_extraction(text, model=emb_model)
                vectors.append(self._to_1d(result))
            except Exception as err:
                logger.error("Embedding failed: %s", err)
                raise RuntimeError(
                    f"Embedding failed for {emb_model}. Ensure HF_TOKEN is set and the model is available."
                ) from err
        return vectors

    @staticmethod
    def _to_1d(result: Any) -> list[float]:
        import numpy as np

        arr = np.array(result, dtype=float)
        if arr.ndim == 1:
            return arr.tolist()
        if arr.ndim == 2:
            return arr.mean(axis=0).tolist()
        return arr.reshape(-1).tolist()


def extract_json_block(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


hf_service = HFService()
