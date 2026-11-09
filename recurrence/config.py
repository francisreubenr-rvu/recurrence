"""Settings from environment (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional
    pass


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass
class Settings:
    hindsight_url: str
    hindsight_api_key: str | None
    bank_id: str
    groq_api_key: str | None
    groq_base_url: str
    model: str
    fallback_model: str
    offline: bool
    # Writes (resolve, preference) require this token when set. With no token,
    # writes are allowed only in offline demo mode and refused in live mode.
    write_token: str | None = None
    ask_rate_per_min: int = 30
    trust_proxy: bool = False
    ingest_dedupe_seconds: int = 300

    @classmethod
    def from_env(cls, offline: bool | None = None) -> "Settings":
        off = offline if offline is not None else os.getenv("RECURRENCE_OFFLINE", "0") == "1"
        return cls(
            hindsight_url=os.getenv("HINDSIGHT_API_URL") or os.getenv("HINDSIGHT_URL", "http://localhost:8888"),
            hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
            bank_id=os.getenv("HINDSIGHT_BANK_ID", "recurrence-tamarind-sre"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            fallback_model=os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3-32b"),
            offline=off,
            write_token=os.getenv("RECURRENCE_WRITE_TOKEN") or None,
            ask_rate_per_min=_int_env("RECURRENCE_ASK_RATE_PER_MIN", 30),
            trust_proxy=os.getenv("RECURRENCE_TRUST_PROXY", "0") == "1",
            ingest_dedupe_seconds=_int_env("RECURRENCE_INGEST_DEDUPE_SECONDS", 300),
        )

    @property
    def writes_enabled(self) -> bool:
        return bool(self.write_token) or self.offline


def build_memory(s: Settings):
    from .memory import FakeMemory, HindsightMemory

    if s.offline:
        return FakeMemory()
    return HindsightMemory(base_url=s.hindsight_url, bank_id=s.bank_id, api_key=s.hindsight_api_key)


def build_llm(s: Settings):
    from .llm import GroqLLM, OfflineLLM

    if s.offline or not s.groq_api_key:
        return OfflineLLM()
    return GroqLLM(api_key=s.groq_api_key, base_url=s.groq_base_url, model=s.model, fallback_model=s.fallback_model)
