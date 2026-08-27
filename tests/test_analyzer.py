import pytest
import sqlite3
from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer
from storage.db import DatabaseManager


class TestKAPAnalyzer:
    """KAPAnalyzer yerel LLM analiz birim testleri."""

    def test_build_prompt(self):
        analyzer = KAPAnalyzer()
        notif = KapNotification(
            id="TEST-001",
            stock_code="THYAO",
            title="Yeni Hat Açılışı",
            publish_date="2026-08-26 12:00:00",
            summary="Melbourne uçuşları başlamıştır.",
        )
        prompt = analyzer.build_prompt(notif)
        assert "THYAO" in prompt
        assert "Melbourne" in prompt
        assert "AL" in prompt and "SAT" in prompt and "NÖTR" in prompt

    def test_parse_llm_response_clean(self):
        analyzer = KAPAnalyzer()
        raw = '{"recommendation": "AL", "reasoning": "Yeni hatlar gelir artışı sağlar.", "confidence": 4}'
        parsed = analyzer._parse_llm_response(raw)
        assert parsed is not None
        assert parsed["recommendation"] == "AL"
        assert parsed["confidence"] == 4
        assert "gelir artışı" in parsed["reasoning"]

    def test_parse_llm_response_with_markdown_blocks(self):
        analyzer = KAPAnalyzer()
        raw = '```json\n{"recommendation": "SAT", "reasoning": "Zarar açıklandı.", "confidence": 5}\n```'
        parsed = analyzer._parse_llm_response(raw)
        assert parsed is not None
        assert parsed["recommendation"] == "SAT"
        assert parsed["confidence"] == 5

    def test_parse_llm_response_invalid_returns_none(self):
        analyzer = KAPAnalyzer()
        raw = "Geçersiz metin, JSON yok."
        parsed = analyzer._parse_llm_response(raw)
        assert parsed is None
