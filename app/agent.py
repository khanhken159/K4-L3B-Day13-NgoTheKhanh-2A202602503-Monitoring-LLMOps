from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, scrub_text, summarize_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, observe, propagate_attributes, tracing_enabled


class _NoopObservation:
    """Keep the request path working when tracing is disabled or unavailable."""

    def update(self, **_: Any) -> None:
        return None


@contextmanager
def _child_observation(
    client: Any,
    *,
    enabled: bool,
    name: str,
    as_type: str,
    **attributes: Any,
):
    start_observation = getattr(client, "start_as_current_observation", None)
    if not enabled or not callable(start_observation):
        yield _NoopObservation()
        return

    with start_observation(name=name, as_type=as_type, **attributes) as observation:
        yield observation


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(name="lab-agent-run", as_type="agent", capture_input=False, capture_output=False)
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        langfuse_client = get_langfuse_client()
        safe_feature = scrub_text(feature)
        with propagate_attributes(
            user_id=hash_user_id(user_id),
            session_id=scrub_text(session_id),
            tags=["lab", safe_feature, self.model],
            trace_name="day13-agent-request",
            environment=os.getenv("APP_ENV", "dev"),
            metadata={
                "feature": safe_feature,
                "model": self.model,
                "correlation_id": scrub_text(correlation_id),
            },
        ):
            started = time.perf_counter()
            with _child_observation(
                langfuse_client,
                enabled=tracing_enabled(),
                name="retrieve-context",
                as_type="retriever",
                input={"query_preview": summarize_text(message)},
            ) as retrieval_observation:
                docs = retrieve(message)
                retrieval_observation.update(output={"document_count": len(docs)})

            prompt = resolve_prompt(
                langfuse_client,
                feature=feature,
                docs=docs,
                message=message,
                enabled=tracing_enabled(),
            )
            langfuse_client.update_current_span(
                metadata={
                    "doc_count": len(docs),
                    "query_preview": summarize_text(message),
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error or "",
                },
                version=prompt.version,
            )
            with propagate_attributes(prompt=prompt.managed_prompt):
                with _child_observation(
                    langfuse_client,
                    enabled=tracing_enabled(),
                    name="fake-llm-generate",
                    as_type="generation",
                    model=self.model,
                    input={"prompt_preview": summarize_text(prompt.text, max_len=240)},
                ) as generation_observation:
                    response = self.llm.generate(prompt.text)
                    cost_usd = self._estimate_cost(
                        response.usage.input_tokens, response.usage.output_tokens
                    )
                    input_cost_usd = response.usage.input_tokens / 1_000_000 * 3
                    output_cost_usd = response.usage.output_tokens / 1_000_000 * 15
                    generation_observation.update(
                        output=summarize_text(response.text, max_len=240),
                        usage_details={
                            "input": response.usage.input_tokens,
                            "output": response.usage.output_tokens,
                        },
                        cost_details={
                            "input": input_cost_usd,
                            "output": output_cost_usd,
                            "total": input_cost_usd + output_cost_usd,
                        },
                    )
            quality_score = self._heuristic_quality(message, response.text, docs)
            latency_ms = int((time.perf_counter() - started) * 1000)

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
