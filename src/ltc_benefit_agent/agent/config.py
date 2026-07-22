"""Agent provider 與環境設定；模型字串一律由環境變數載入。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv


class AgentProvider(StrEnum):
    GEMINI = "gemini"
    F1_OLLAMA = "f1_ollama"
    GEMMA3_BASELINE = "gemma3_baseline"


@dataclass(frozen=True, slots=True)
class AgentSettings:
    provider: AgentProvider
    gemini_model: str
    ollama_f1_model: str
    ollama_baseline_model: str
    ollama_base_url: str
    is_space: bool
    ollama_timeout_seconds: float = 60.0

    @property
    def selected_model(self) -> str:
        if self.provider is AgentProvider.GEMINI:
            return self.gemini_model
        if self.provider is AgentProvider.F1_OLLAMA:
            return self.ollama_f1_model
        return self.ollama_baseline_model

    @classmethod
    def from_env(
        cls,
        *,
        provider: AgentProvider | None = None,
        dotenv_path: Path | None = None,
    ) -> "AgentSettings":
        if dotenv_path is None:
            dotenv_path = Path(__file__).resolve().parents[3] / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=False)
        selected = provider or AgentProvider(
            os.getenv("AGENT_PROVIDER", AgentProvider.GEMINI.value)
        )
        try:
            ollama_timeout_seconds = float(
                os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")
            )
        except ValueError as exc:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS 必須是數字") from exc
        settings = cls(
            provider=selected,
            gemini_model=os.getenv("GEMINI_MODEL", ""),
            ollama_f1_model=os.getenv("OLLAMA_F1_MODEL", ""),
            ollama_baseline_model=os.getenv("OLLAMA_BASELINE_MODEL", ""),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            is_space=bool(os.getenv("SPACE_ID")),
            ollama_timeout_seconds=ollama_timeout_seconds,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not isinstance(self.provider, AgentProvider):
            raise TypeError("provider 必須是 AgentProvider")
        if self.is_space and self.provider is not AgentProvider.GEMINI:
            raise ValueError("HF Space 環境只允許 Gemini provider")
        model_env = {
            AgentProvider.GEMINI: ("GEMINI_MODEL", self.gemini_model),
            AgentProvider.F1_OLLAMA: ("OLLAMA_F1_MODEL", self.ollama_f1_model),
            AgentProvider.GEMMA3_BASELINE: (
                "OLLAMA_BASELINE_MODEL",
                self.ollama_baseline_model,
            ),
        }
        env_name, model_name = model_env[self.provider]
        if not model_name.strip():
            raise ValueError(f"請在 .env 設定 {env_name}")
        if self.provider is not AgentProvider.GEMINI and not self.ollama_base_url.strip():
            raise ValueError("OLLAMA_BASE_URL 不得為空")
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS 必須大於 0")
