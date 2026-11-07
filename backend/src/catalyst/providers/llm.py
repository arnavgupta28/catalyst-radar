"""LLM providers. Every call returns a validated Pydantic object or raises.

- OpenAICompatLLM : LM Studio (localhost:1234/v1) and Databricks Model Serving (/serving-endpoints)
- ClaudeLLM       : Anthropic Messages API
- MockLLM         : deterministic answers built from the context (offline, free, used in tests)
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from catalyst.schemas import AlertDraft, Fact, TriageVerdict

T = TypeVar("T", bound=BaseModel)
Role = Literal["triage", "writer"]


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str

    def model_for(self, role: Role) -> str: ...

    def complete_json(
        self, role: Role, system: str, user: str, schema: type[T], context: dict[str, Any] | None = None
    ) -> T: ...


_THINK = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str) -> str:
    """Strip Qwen <think> blocks / code fences and return the outermost JSON object."""
    text = _THINK.sub("", text).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"no JSON object in model output: {text[:200]!r}")
    return text[start : end + 1]


def _validate(schema: type[T], text: str) -> T:
    return schema.model_validate_json(extract_json(text))


# ------------------------------------------------------------------ OpenAI-compatible
class OpenAICompatLLM:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        triage_model: str,
        writer_model: str,
        timeout: float = 180,
        use_json_schema: bool = True,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.models = {"triage": triage_model, "writer": writer_model}
        self.use_json_schema = use_json_schema
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(headers=headers, timeout=timeout)

    def model_for(self, role: Role) -> str:
        return self.models[role]

    def _chat(self, model: str, messages: list[dict[str, str]], schema: type[BaseModel] | None) -> str:
        body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if schema is not None and self.use_json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": True},
            }
        resp = self._http.post(f"{self.base_url}/chat/completions", json=body)
        if resp.status_code == 400 and schema is not None and self.use_json_schema:
            # Some endpoints don't support json_schema: fall back to prompt-only JSON.
            self.use_json_schema = False
            return self._chat(model, messages, schema)
        if resp.status_code >= 400:
            raise LLMError(f"{self.name} HTTP {resp.status_code}: {resp.text[:300]}")
        return str(resp.json()["choices"][0]["message"]["content"] or "")

    def complete_json(
        self, role: Role, system: str, user: str, schema: type[T], context: dict[str, Any] | None = None
    ) -> T:
        model = self.model_for(role)
        if not model:
            raise LLMError(f"{self.name}: no model configured for role {role!r}")
        sys_prompt = (
            f"{system}\n\nReply with ONLY a JSON object matching this schema:\n{json.dumps(schema.model_json_schema())}"
        )
        messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]
        text = self._chat(model, messages, schema)
        try:
            return _validate(schema, text)
        except (ValidationError, LLMError) as exc:
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That was invalid: {exc}. Return only the corrected JSON."},
            ]
            return _validate(schema, self._chat(model, messages, schema))


# ------------------------------------------------------------------ Claude
class ClaudeLLM:
    name = "claude"

    def __init__(self, api_key: str, triage_model: str, writer_model: str, timeout: float = 120) -> None:
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.models = {"triage": triage_model, "writer": writer_model}
        self._http = httpx.Client(
            timeout=timeout,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        )

    def model_for(self, role: Role) -> str:
        return self.models[role]

    def complete_json(
        self, role: Role, system: str, user: str, schema: type[T], context: dict[str, Any] | None = None
    ) -> T:
        body = {
            "model": self.model_for(role),
            "max_tokens": 1500,
            "temperature": 0.2,
            "system": f"{system}\n\nReply with ONLY a JSON object matching this schema:\n"
            f"{json.dumps(schema.model_json_schema())}",
            "messages": [{"role": "user", "content": user}],
        }
        resp = self._http.post("https://api.anthropic.com/v1/messages", json=body)
        if resp.status_code >= 400:
            raise LLMError(f"claude HTTP {resp.status_code}: {resp.text[:300]}")
        text = "".join(b.get("text", "") for b in resp.json().get("content", []))
        return _validate(schema, text)


# ------------------------------------------------------------------ Mock
class MockLLM:
    """Deterministic, schema-valid answers from the context. Lets the whole pipeline run offline."""

    name = "mock"

    def model_for(self, role: Role) -> str:
        return f"mock-{role}"

    def complete_json(
        self, role: Role, system: str, user: str, schema: type[T], context: dict[str, Any] | None = None
    ) -> T:
        ctx = context or {}
        if schema is TriageVerdict:
            score = int(ctx.get("materiality", 60))
            return schema.model_validate(
                {
                    "material": score >= int(ctx.get("threshold", 55)),
                    "event_type": ctx.get("event_type", "news"),
                    "materiality": score,
                    "reason": f"Rule match: {ctx.get('event_type', 'news')} (mock triage)",
                }
            )
        if schema is AlertDraft:
            return schema.model_validate(_mock_draft(ctx).model_dump())
        raise LLMError(f"MockLLM has no template for {schema.__name__}")


def _article(word: str) -> str:
    return "An" if word[:1].lower() in "aeiou" else "A"


def _mock_draft(ctx: dict[str, Any]) -> AlertDraft:
    company = ctx.get("company", "The company")
    title = ctx.get("title", "New development")
    etype = ctx.get("event_type", "news")
    sentiment = ctx.get("sentiment_hint", "mixed")
    score = int(ctx.get("materiality", 60))
    ev_ids = [e["evidence_id"] for e in ctx.get("evidence", [])]
    outlets = sorted({e.get("outlet") or e.get("source_id", "") for e in ctx.get("evidence", [])})
    return AlertDraft(
        sentiment=sentiment if sentiment in {"positive", "negative", "mixed", "neutral"} else "mixed",
        priority="High" if score >= 75 else "Medium" if score >= 60 else "Low",
        headline=title,
        what_happened=f"{company}: {title}. Reported by {', '.join(outlets) or 'one source'}.",
        why_it_matters=f"{_article(etype)} {etype.replace('_', ' ')} can change the outlook for {company}; "
        "the size relative to the business decides how much.",
        risks="Details may be incomplete; the market may already have priced this in.",
        bull_case="If confirmed and material, it supports future growth or reduces risk.",
        bear_case="It may be smaller than it sounds, or come with costs not yet disclosed.",
        next_steps="Read the original filing, compare with the latest results, and watch for follow-ups.",
        facts=[
            Fact(
                key="Headline",
                value=title,
                verification="confirmed" if ev_ids else "unconfirmed",
                evidence_ids=ev_ids[:1],
            )
        ],
    )
