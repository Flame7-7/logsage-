"""
LogSage AI — AI Analysis Service
Root cause analysis, incident summarization, and RAG-powered recommendations.
Uses Anthropic Claude with structured outputs.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

import anthropic
import structlog

from ai.embeddings.embedding_service import (
    embed_incident,
    find_similar_incidents,
    find_similar_logs,
)
from core.config import settings
from models.models import Incident, LogEntry
from schemas.schemas import RootCause, TimelineEvent

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_anthropic_client: anthropic.AsyncAnthropic | None = None


def get_llm_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
    return _anthropic_client


# ── Prompts ───────────────────────────────────────────────────────────────────

ROOT_CAUSE_SYSTEM = """You are LogSage AI, an expert incident response system analyzing production logs.
Your job is to analyze log patterns, identify root causes, and provide actionable fixes.
Always respond with valid JSON only — no markdown, no explanation outside the JSON structure.
Be precise, technical, and concise."""

ROOT_CAUSE_PROMPT = """Analyze the following production incident:

INCIDENT TITLE: {title}
SEVERITY: {severity}
LOG COUNT: {log_count}
AFFECTED SERVICES: {services}

REPRESENTATIVE LOG MESSAGES:
{log_samples}

SIMILAR PAST INCIDENTS (for context):
{similar_incidents}

Respond with this exact JSON structure:
{{
  "root_causes": [
    {{"cause": "string", "confidence": 0.0-1.0, "category": "infrastructure|code|config|network|dependency"}}
  ],
  "recommended_fixes": ["fix 1", "fix 2", "fix 3"],
  "ai_confidence": 0.0-1.0,
  "executive_summary": "2-3 sentence summary",
  "technical_details": "detailed technical analysis",
  "impact_assessment": "what was/is impacted",
  "prevention_steps": ["step 1", "step 2"]
}}"""

TIMELINE_PROMPT = """Generate an incident timeline from these chronologically ordered log entries:

{log_entries}

Respond with JSON only:
{{
  "timeline": [
    {{"timestamp": "ISO8601", "event": "description", "level": "ERROR|WARNING|INFO", "service": "service_name"}}
  ],
  "chain_summary": "1-2 sentence causal chain description"
}}"""


# ── Core analysis functions ───────────────────────────────────────────────────

async def analyze_root_cause(
    incident: Incident,
    log_entries: list[LogEntry],
    use_rag: bool = True,
) -> dict:
    """
    Perform AI-powered root cause analysis.
    Optionally retrieves similar past incidents via RAG.
    """
    start = time.monotonic()
    client = get_llm_client()

    # Prepare log samples (top 20 most relevant)
    log_samples = "\n".join(
        f"[{e.timestamp.strftime('%H:%M:%S')}] [{e.level}] {e.service or 'unknown'}: {e.message}"
        for e in log_entries[:20]
    )

    # RAG: retrieve similar past incidents
    similar_text = "No similar past incidents found."
    similar_incidents_data = []
    if use_rag:
        query = f"{incident.title} {log_samples[:500]}"
        similar = await find_similar_incidents(query, top_k=3)
        if similar:
            similar_items = []
            for s in similar:
                meta = s.get("metadata", {})
                similar_items.append(
                    f"- {meta.get('title', 'Unknown')} "
                    f"(similarity: {1 - s['distance']:.0%}): "
                    f"{s['document'][:200]}"
                )
            similar_text = "\n".join(similar_items)
            similar_incidents_data = similar

    services = ", ".join(incident.affected_services or ["unknown"])
    prompt = ROOT_CAUSE_PROMPT.format(
        title=incident.title,
        severity=incident.severity,
        log_count=incident.log_count,
        services=services,
        log_samples=log_samples,
        similar_incidents=similar_text,
    )

    response = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
        system=ROOT_CAUSE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_json = response.content[0].text
    import json
    try:
        result = json.loads(raw_json)
    except json.JSONDecodeError:
        # Strip possible markdown fences
        cleaned = raw_json.strip().strip("```json").strip("```").strip()
        result = json.loads(cleaned)

    elapsed_ms = (time.monotonic() - start) * 1000

    # Parse root causes
    root_causes = [
        RootCause(
            cause=rc["cause"],
            confidence=float(rc.get("confidence", 0.5)),
            category=rc.get("category"),
        )
        for rc in result.get("root_causes", [])
    ]

    # Embed this incident for future RAG retrieval
    summary_text = f"{incident.title}. {result.get('executive_summary', '')}"
    await embed_incident(
        incident_id=incident.id,
        text=summary_text,
        metadata={
            "title": incident.title,
            "severity": str(incident.severity),
            "services": services,
        },
    )

    logger.info(
        "Root cause analysis complete",
        incident_id=incident.id,
        confidence=result.get("ai_confidence"),
        root_causes=len(root_causes),
        elapsed_ms=round(elapsed_ms, 2),
    )

    return {
        "root_causes": root_causes,
        "recommended_fixes": result.get("recommended_fixes", []),
        "ai_confidence": float(result.get("ai_confidence", 0.5)),
        "ai_summary": result.get("executive_summary", ""),
        "executive_summary": result.get("executive_summary", ""),
        "technical_details": result.get("technical_details", ""),
        "impact_assessment": result.get("impact_assessment", ""),
        "prevention_steps": result.get("prevention_steps", []),
        "similar_incidents": similar_incidents_data,
        "model_used": settings.LLM_MODEL,
        "token_usage": response.usage.output_tokens,
        "analysis_time_ms": elapsed_ms,
    }


async def generate_timeline(
    log_entries: list[LogEntry],
) -> tuple[list[TimelineEvent], str]:
    """Generate an AI-summarized incident timeline."""
    if not log_entries:
        return [], "No log entries provided."

    client = get_llm_client()

    # Sort chronologically
    sorted_entries = sorted(log_entries, key=lambda e: e.timestamp)

    entries_text = "\n".join(
        f"{e.timestamp.isoformat()} [{e.level}] {e.service or 'unknown'}: {e.message}"
        for e in sorted_entries[:50]
    )

    response = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1024,
        temperature=0.0,
        system="You are a log analysis AI. Respond with JSON only.",
        messages=[{"role": "user", "content": TIMELINE_PROMPT.format(log_entries=entries_text)}],
    )

    import json
    raw = response.content[0].text.strip().strip("```json").strip("```").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: generate timeline from raw data
        return _fallback_timeline(sorted_entries), "Timeline generated from log sequence."

    timeline_events = []
    for item in data.get("timeline", []):
        try:
            ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            ts = datetime.utcnow()
        timeline_events.append(
            TimelineEvent(
                timestamp=ts,
                event=item.get("event", ""),
                level=item.get("level"),
                service=item.get("service"),
            )
        )

    chain_summary = data.get("chain_summary", "")
    return timeline_events, chain_summary


def _fallback_timeline(entries: list[LogEntry]) -> list[TimelineEvent]:
    """Build basic timeline without LLM when API unavailable."""
    return [
        TimelineEvent(
            timestamp=e.timestamp,
            event=e.message[:200],
            level=str(e.level),
            service=e.service,
        )
        for e in entries[:30]
    ]


async def summarize_cluster(
    cluster_name: str,
    representative_messages: list[str],
    log_count: int,
) -> str:
    """Generate a short cluster description using LLM."""
    client = get_llm_client()
    msgs_text = "\n".join(f"- {m}" for m in representative_messages[:5])
    prompt = (
        f"In 1-2 sentences, describe this log cluster named '{cluster_name}' "
        f"containing {log_count} events:\n{msgs_text}\n\n"
        "Be technical and concise. No markdown."
    )
    response = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=150,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
