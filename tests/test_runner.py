import pytest
import asyncio
from unittest.mock import AsyncMock
from main import BorsaAIService
from ingestion.kap_feed import KAPFeedFetcher
from storage.db import db


@pytest.mark.asyncio
async def test_service_start_and_graceful_stop():
    fetcher = KAPFeedFetcher(watchlist=["THYAO"], disclosure_class="ODA")
    fetcher.fetch_latest = AsyncMock(return_value=[])
    
    analyzer = AsyncMock()
    analyzer.analyze_unprocessed = AsyncMock(return_value=0)
    analyzer.model_name = "test-model"
    analyzer.base_url = "http://localhost:11434"
    
    service = BorsaAIService(fetcher=fetcher, analyzer=analyzer)
    task = asyncio.create_task(service.start())
    await asyncio.sleep(0.05)
    service.stop()
    await task
    assert service.is_running is False
    
    stats = db.get_stats()
    assert stats["total_notifications"] >= 0
