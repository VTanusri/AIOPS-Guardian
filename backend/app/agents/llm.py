from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas import StructuredRCA


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate_rca(self, prompt: str, fallback: StructuredRCA) -> StructuredRCA:
        raise NotImplementedError

    @abstractmethod
    async def answer(self, prompt: str, fallback_text: str) -> str:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    name = "mock"

    async def generate_rca(self, prompt: str, fallback: StructuredRCA) -> StructuredRCA:
        # Never invent metrics — return deterministic structured RCA from engine
        if fallback.confidence < 40:
            fallback.reasoning_summary = (
                "Insufficient evidence for a high-confidence RCA. "
                "Collected signals are weak or contradictory; gather more telemetry before acting."
            )
            fallback.root_cause = fallback.root_cause or "Insufficient Evidence"
        else:
            fallback.reasoning_summary = (
                f"Based solely on provided telemetry and retrieved knowledge, the most probable cause is "
                f"{fallback.root_cause} with explainable score {fallback.confidence:.0f}/100. "
                "No actions were executed."
            )
        return fallback

    async def answer(self, prompt: str, fallback_text: str) -> str:
        return fallback_text


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def _chat(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

    async def generate_rca(self, prompt: str, fallback: StructuredRCA) -> StructuredRCA:
        try:
            raw = await self._chat(prompt)
            parsed = _extract_json(raw)
            # Force confidence from deterministic engine; LLM must not invent score
            parsed["confidence"] = fallback.confidence
            parsed["confidence_label"] = fallback.confidence_label
            parsed["score_breakdown"] = fallback.score_breakdown
            # Ensure evidence lists are subsets / grounded — prefer engine lists if LLM empty
            if not parsed.get("supporting_evidence"):
                parsed["supporting_evidence"] = fallback.supporting_evidence
            if "contradicting_evidence" not in parsed:
                parsed["contradicting_evidence"] = fallback.contradicting_evidence
            if not parsed.get("recommendations"):
                parsed["recommendations"] = fallback.recommendations
            if not parsed.get("retrieved_knowledge"):
                parsed["retrieved_knowledge"] = fallback.retrieved_knowledge
            parsed["root_cause"] = parsed.get("root_cause") or fallback.root_cause
            parsed["severity"] = parsed.get("severity") or fallback.severity
            return StructuredRCA.model_validate(parsed)
        except Exception:
            return await MockLLMProvider().generate_rca(prompt, fallback)

    async def answer(self, prompt: str, fallback_text: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                resp.raise_for_status()
                text = resp.json().get("response", "").strip()
                return text or fallback_text
        except Exception:
            return fallback_text


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def ollama_available(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


_provider: LLMProvider | None = None


async def get_llm_provider() -> LLMProvider:
    global _provider
    settings = get_settings()
    if settings.llm_provider == "mock":
        _provider = MockLLMProvider()
        return _provider
    if settings.llm_provider == "ollama":
        _provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
        return _provider
    # auto
    if await ollama_available(settings.ollama_base_url):
        _provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    else:
        _provider = MockLLMProvider()
    return _provider
