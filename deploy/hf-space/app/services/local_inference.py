from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
import torch
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer

from app.config import get_settings

logger = logging.getLogger(__name__)

# Small/medium models intended for local transformers (variant 2)
LOCAL_CHAT_MODELS = {
    "BioMistral/BioMistral-7B",
    "microsoft/biogpt",
    "microsoft/biogpt-large",
    "stanford-crfm/BioMedLM",
    "google/medgemma-4b-it",
    "m42-health/Llama3-Med42-8B",
}

LOCAL_EMBED_MODELS = {
    "NeuML/pubmedbert-base-embeddings",
    "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
    "dmis-lab/biobert-v1.1",
}


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def pick_dtype(device: str) -> torch.dtype:
    if device in {"mps", "cuda"}:
        return torch.float16
    return torch.float32


class LocalInferenceService:
    """Load small/medium HF models locally with transformers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chat_models: dict[str, Any] = {}
        self._chat_tokenizers: dict[str, Any] = {}
        self._embed_models: dict[str, Any] = {}
        self._embed_tokenizers: dict[str, Any] = {}
        self.device = pick_device()
        self.dtype = pick_dtype(self.device)

    def supports_chat(self, model_id: str) -> bool:
        settings = get_settings()
        if not settings.local_inference:
            return False
        return model_id in LOCAL_CHAT_MODELS or model_id == settings.local_chat_model

    def supports_embed(self, model_id: str) -> bool:
        settings = get_settings()
        if not settings.local_inference:
            return False
        return model_id in LOCAL_EMBED_MODELS or model_id == settings.embedding_model

    def _token(self) -> str | None:
        token = (get_settings().hf_token or "").strip()
        if not token or token.startswith("hf_your_token"):
            return None
        return token

    def _load_chat(self, model_id: str) -> tuple[Any, Any]:
        if model_id in self._chat_models:
            return self._chat_models[model_id], self._chat_tokenizers[model_id]

        with self._lock:
            if model_id in self._chat_models:
                return self._chat_models[model_id], self._chat_tokenizers[model_id]

            logger.info("Loading local chat model %s on %s (%s)", model_id, self.device, self.dtype)
            token = self._token()
            tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                token=token,
                dtype=self.dtype,
                low_cpu_mem_usage=True,
            )
            model.to(self.device)
            model.eval()
            self._chat_models[model_id] = model
            self._chat_tokenizers[model_id] = tokenizer
            logger.info("Local chat model ready: %s", model_id)
            return model, tokenizer

    def _load_embed(self, model_id: str) -> tuple[Any, Any]:
        if model_id in self._embed_models:
            return self._embed_models[model_id], self._embed_tokenizers[model_id]

        with self._lock:
            if model_id in self._embed_models:
                return self._embed_models[model_id], self._embed_tokenizers[model_id]

            logger.info("Loading local embedding model %s on %s", model_id, self.device)
            token = self._token()
            tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
            model = AutoModel.from_pretrained(model_id, token=token)
            model.to(self.device if self.device != "mps" else "cpu")  # BERT on CPU is stable on Mac
            model.eval()
            self._embed_models[model_id] = model
            self._embed_tokenizers[model_id] = tokenizer
            return model, tokenizer

    def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 512,
        temperature: float = 0.4,
    ) -> str:
        try:
            return self._chat_once(
                model_id, messages, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as err:
            fallback = "microsoft/biogpt"
            if model_id != fallback:
                logger.warning(
                    "Local chat failed for %s (%s) — falling back to %s",
                    model_id,
                    err,
                    fallback,
                )
                return self._chat_once(
                    fallback, messages, max_tokens=max_tokens, temperature=temperature
                )
            raise

    def _chat_once(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        model, tokenizer = self._load_chat(model_id)
        prompt = self._messages_to_prompt(tokenizer, messages)

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3072)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max(32, min(max_tokens, 1024)),
            "do_sample": temperature > 0.05,
            "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if gen_kwargs["do_sample"]:
            gen_kwargs["temperature"] = max(0.1, float(temperature))
            gen_kwargs["top_p"] = 0.9

        with torch.no_grad():
            output_ids = model.generate(**inputs, **gen_kwargs)

        new_tokens = output_ids[0][inputs["input_ids"].shape[-1] :]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        return text

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        model, tokenizer = self._load_embed(model_id)
        device = next(model.parameters()).device
        vectors: list[list[float]] = []
        for text in texts:
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                out = model(**inputs)
            # mean pool last_hidden_state with attention mask
            hidden = out.last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-9)
            pooled = (summed / counts).squeeze(0).detach().cpu().numpy().astype(float)
            vectors.append(pooled.tolist())
        return vectors

    @staticmethod
    def _messages_to_prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
        if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                pass

        parts: list[str] = []
        for m in messages:
            role = m.get("role", "user").upper()
            parts.append(f"{role}: {m.get('content', '')}")
        parts.append("ASSISTANT:")
        return "\n\n".join(parts)


local_inference = LocalInferenceService()
