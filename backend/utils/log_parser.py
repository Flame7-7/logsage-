"""
LogSage AI — Log Normalizer
Parse and normalize TXT, JSON, CSV log formats into unified LogEntry objects.
"""

import csv
import io
import json
import re
import uuid
from datetime import datetime
from typing import Iterator

import chardet
import structlog

from models.models import LogEntry, LogLevel, LogSource

logger = structlog.get_logger(__name__)

# ── Timestamp patterns ────────────────────────────────────────────────────────
TIMESTAMP_PATTERNS = [
    (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", "%Y-%m-%dT%H:%M:%S"),
    (r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?", "%Y-%m-%d %H:%M:%S"),
    (r"\d{2}/\w+/\d{4}:\d{2}:\d{2}:\d{2}", "%d/%b/%Y:%H:%M:%S"),
    (r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", "%b %d %H:%M:%S"),
]

LEVEL_PATTERNS = re.compile(
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b", re.IGNORECASE
)

SERVICE_PATTERNS = re.compile(
    r"\[([a-zA-Z0-9_\-\.]+)\]|\b(gateway|redis|db|worker|api|cache|shard|queue)\b",
    re.IGNORECASE,
)


def detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw[:8192])
    return result.get("encoding") or "utf-8"


def parse_timestamp(text: str) -> datetime | None:
    for pattern, fmt in TIMESTAMP_PATTERNS:
        match = re.search(pattern, text)
        if match:
            ts_str = match.group(0).strip()
            try:
                # Truncate microseconds for simpler formats
                ts_str = ts_str[:19]
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
    return None


def parse_level(text: str) -> LogLevel:
    match = LEVEL_PATTERNS.search(text)
    if match:
        lvl = match.group(1).upper()
        if lvl in ("WARN", "WARNING"):
            return LogLevel.WARNING
        if lvl == "FATAL":
            return LogLevel.CRITICAL
        if lvl == "TRACE":
            return LogLevel.DEBUG
        try:
            return LogLevel(lvl)
        except ValueError:
            pass
    # Heuristic fallback
    text_lower = text.lower()
    if any(w in text_lower for w in ["error", "fail", "exception", "crash", "panic"]):
        return LogLevel.ERROR
    if any(w in text_lower for w in ["warn", "timeout", "retry", "slow"]):
        return LogLevel.WARNING
    if any(w in text_lower for w in ["critical", "fatal", "oom", "killed"]):
        return LogLevel.CRITICAL
    return LogLevel.INFO


def parse_service(text: str) -> str | None:
    match = SERVICE_PATTERNS.search(text)
    if match:
        return (match.group(1) or match.group(2) or "").lower() or None
    return None


# ── Format-specific parsers ───────────────────────────────────────────────────

def _parse_json_line(line: str, session_id: str, source: LogSource) -> LogEntry | None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Normalize common JSON log field names
    msg = (
        data.get("message")
        or data.get("msg")
        or data.get("text")
        or data.get("log")
        or str(data)
    )
    level_raw = str(
        data.get("level") or data.get("severity") or data.get("lvl") or "INFO"
    )
    ts_raw = data.get("timestamp") or data.get("time") or data.get("ts") or data.get("@timestamp")
    service = data.get("service") or data.get("app") or data.get("logger") or parse_service(msg)

    if ts_raw:
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            ts = parse_timestamp(str(ts_raw)) or datetime.utcnow()
    else:
        ts = datetime.utcnow()

    extra = {k: v for k, v in data.items()
             if k not in {"message", "msg", "text", "level", "severity", "timestamp", "time", "service"}}

    return LogEntry(
        id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=ts,
        level=parse_level(level_raw),
        source=source,
        service=service,
        message=str(msg)[:5000],
        raw_line=line[:2000],
        extra_fields=extra or None,
    )


def _parse_text_line(line: str, session_id: str, source: LogSource) -> LogEntry | None:
    line = line.strip()
    if not line:
        return None

    ts = parse_timestamp(line) or datetime.utcnow()
    level = parse_level(line)
    service = parse_service(line)

    # Strip timestamp/level prefix to get clean message
    msg = line
    for pattern, _ in TIMESTAMP_PATTERNS:
        msg = re.sub(pattern, "", msg, count=1)
    msg = LEVEL_PATTERNS.sub("", msg, count=1)
    msg = re.sub(r"^\s*[\[\(]?[A-Z]+[\]\)]?\s*", "", msg).strip() or line

    return LogEntry(
        id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=ts,
        level=level,
        source=source,
        service=service,
        message=msg[:5000],
        raw_line=line[:2000],
    )


def _parse_csv_content(
    content: str, session_id: str, source: LogSource
) -> Iterator[LogEntry]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return

    fieldnames_lower = [f.lower() for f in reader.fieldnames]

    def find_field(candidates: list[str]) -> str | None:
        for c in candidates:
            for i, fn in enumerate(fieldnames_lower):
                if c in fn:
                    return reader.fieldnames[i]
        return None

    msg_field = find_field(["message", "msg", "log", "text", "event"])
    ts_field = find_field(["timestamp", "time", "date", "ts"])
    level_field = find_field(["level", "severity", "lvl"])
    service_field = find_field(["service", "app", "source", "component"])

    for row in reader:
        msg = row.get(msg_field or "", "") if msg_field else str(row)
        if not msg:
            continue

        ts_raw = row.get(ts_field, "") if ts_field else ""
        ts = parse_timestamp(ts_raw) or datetime.utcnow()

        level_raw = row.get(level_field, "INFO") if level_field else "INFO"
        service = row.get(service_field) if service_field else parse_service(msg)

        extra = {k: v for k, v in row.items()
                 if k not in {msg_field, ts_field, level_field, service_field} and v}

        yield LogEntry(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=ts,
            level=parse_level(level_raw),
            source=source,
            service=service or None,
            message=str(msg)[:5000],
            raw_line=None,
            extra_fields=extra or None,
        )


# ── Public API ────────────────────────────────────────────────────────────────

def detect_format(content: str) -> str:
    """Heuristically detect log format: 'json', 'csv', or 'text'."""
    sample = content[:2048].strip()
    lines = sample.splitlines()

    if not lines:
        return "text"

    # JSON: first non-empty line parses as JSON object
    for line in lines[:5]:
        line = line.strip()
        if line.startswith("{"):
            try:
                json.loads(line)
                return "json"
            except json.JSONDecodeError:
                break

    # CSV: has consistent comma-delimited header
    if lines[0].count(",") >= 2:
        reader = csv.reader(io.StringIO(sample))
        rows = list(reader)
        if len(rows) > 1 and len(rows[0]) == len(rows[1]):
            return "csv"

    return "text"


def parse_log_content(
    content: bytes | str,
    session_id: str,
    source: LogSource = LogSource.FILE_UPLOAD,
    max_lines: int = 50_000,
) -> tuple[list[LogEntry], int, int]:
    """
    Parse raw log content into LogEntry objects.

    Returns:
        (entries, processed_count, error_count)
    """
    if isinstance(content, bytes):
        encoding = detect_encoding(content)
        content = content.decode(encoding, errors="replace")

    fmt = detect_format(content)
    lines = content.splitlines()[:max_lines]

    entries: list[LogEntry] = []
    errors = 0

    if fmt == "json":
        for line in lines:
            line = line.strip()
            if not line:
                continue
            entry = _parse_json_line(line, session_id, source)
            if entry:
                entries.append(entry)
            else:
                # Fall back to text parse
                entry = _parse_text_line(line, session_id, source)
                if entry:
                    entries.append(entry)
                else:
                    errors += 1

    elif fmt == "csv":
        try:
            entries = list(_parse_csv_content(content, session_id, source))
        except Exception as e:
            logger.warning("CSV parse failed, falling back to text", error=str(e))
            fmt = "text"

    if fmt == "text":
        for line in lines:
            entry = _parse_text_line(line, session_id, source)
            if entry:
                entries.append(entry)
            else:
                errors += 1

    logger.info(
        "Log parsing complete",
        format=fmt,
        total_lines=len(lines),
        parsed=len(entries),
        errors=errors,
        session_id=session_id,
    )
    return entries, len(lines), errors


def parse_stream_line(
    line: str,
    session_id: str,
) -> LogEntry | None:
    """Parse a single line from a live WebSocket stream."""
    line = line.strip()
    if not line:
        return None

    # Try JSON first
    if line.startswith("{"):
        entry = _parse_json_line(line, session_id, LogSource.WEBSOCKET)
        if entry:
            return entry

    return _parse_text_line(line, session_id, LogSource.WEBSOCKET)
