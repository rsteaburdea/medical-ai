from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hf_token: str = ""
    demo_mode: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    default_chat_model: str = "m42-health/Llama3-Med42-8B:featherless-ai"
    embedding_model: str = "NeuML/pubmedbert-base-embeddings"
    pubmed_email: str = "medical-ai@example.com"
    max_history_messages: int = 40

    @property
    def use_demo(self) -> bool:
        """Use offline clinical examiner when no real HF token is configured, or DEMO_MODE=true."""
        if self.demo_mode:
            return True
        token = (self.hf_token or "").strip()
        return not token or token.startswith("hf_your_token")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
