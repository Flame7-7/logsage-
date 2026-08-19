"""
Tests for log_parser utilities.
"""

import pytest
from datetime import datetime
from models.models import LogLevel, LogSource
from utils.log_parser import (
    detect_format,
    parse_log_content,
    parse_stream_line,
    parse_level,
    parse_timestamp,
)


class TestParseLevel:
    def test_error_keyword(self):
        assert parse_level("ERROR: something failed") == LogLevel.ERROR

    def test_warning_keyword(self):
        assert parse_level("WARN: high memory usage") == LogLevel.WARNING

    def test_critical_keyword(self):
        assert parse_level("CRITICAL: system crash") == LogLevel.CRITICAL

    def test_heuristic_error(self):
        assert parse_level("connection refused by server") == LogLevel.ERROR

    def test_heuristic_warn(self):
        assert parse_level("timeout connecting to redis") == LogLevel.WARNING

    def test_default_info(self):
        assert parse_level("server started on port 8000") == LogLevel.INFO


class TestParseTimestamp:
    def test_iso_format(self):
        ts = parse_timestamp("2024-01-15T14:32:01.123Z")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15

    def test_space_format(self):
        ts = parse_timestamp("2024-01-15 14:32:01")
        assert ts is not None
        assert ts.hour == 14

    def test_no_timestamp_returns_none(self):
        ts = parse_timestamp("no timestamp here at all")
        assert ts is None


class TestDetectFormat:
    def test_json_detection(self):
        content = '{"level":"ERROR","message":"failed"}\n{"level":"INFO","message":"ok"}'
        assert detect_format(content) == "json"

    def test_csv_detection(self):
        content = "timestamp,level,service,message\n2024-01-01,ERROR,redis,timeout"
        assert detect_format(content) == "csv"

    def test_text_detection(self):
        content = "2024-01-01 14:00:00 ERROR redis: connection failed"
        assert detect_format(content) == "text"


class TestParseLogContent:
    def test_text_parsing(self):
        content = b"""2024-01-15 12:01:00 ERROR redis: connection timeout
2024-01-15 12:02:00 WARNING gateway: reconnecting
2024-01-15 12:03:00 INFO api: request processed"""
        entries, total, errors = parse_log_content(content, "test-session")
        assert len(entries) == 3
        assert total == 3
        assert errors == 0
        assert entries[0].level == LogLevel.ERROR
        assert entries[1].level == LogLevel.WARNING

    def test_json_parsing(self):
        content = b'{"level":"ERROR","message":"Redis timeout","service":"redis","timestamp":"2024-01-15T12:00:00"}\n{"level":"INFO","message":"Connected","service":"api","timestamp":"2024-01-15T12:00:01"}'
        entries, total, errors = parse_log_content(content, "test-session")
        assert len(entries) == 2
        assert entries[0].service == "redis"
        assert entries[0].level == LogLevel.ERROR

    def test_csv_parsing(self):
        content = b"timestamp,level,service,message\n2024-01-15T12:00:00,ERROR,redis,Connection timeout\n2024-01-15T12:00:01,INFO,api,Started"
        entries, total, errors = parse_log_content(content, "test-session")
        assert len(entries) == 2

    def test_empty_content(self):
        entries, total, errors = parse_log_content(b"", "test-session")
        assert entries == []

    def test_max_lines_limit(self):
        lines = "\n".join(f"INFO line {i}" for i in range(1000))
        entries, total, errors = parse_log_content(
            lines.encode(), "test-session", max_lines=100
        )
        assert len(entries) <= 100


class TestParseStreamLine:
    def test_json_line(self):
        entry = parse_stream_line(
            '{"level":"ERROR","message":"Redis failed","service":"cache"}',
            "stream-session",
        )
        assert entry is not None
        assert entry.level == LogLevel.ERROR
        assert entry.service == "cache"

    def test_text_line(self):
        entry = parse_stream_line(
            "2024-01-15T14:00:00 ERROR redis: timeout", "stream-session"
        )
        assert entry is not None
        assert entry.level == LogLevel.ERROR

    def test_empty_line(self):
        entry = parse_stream_line("", "stream-session")
        assert entry is None
