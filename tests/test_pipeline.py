import asyncio

import pytest

from dataqual.engine import ValidationEngine
from dataqual.models import default_schema
from dataqual.pipeline.consumer import DataConsumer
from dataqual.pipeline.producer import DataProducer
from dataqual.storage import StorageManager


@pytest.mark.asyncio
async def test_pipeline_produces_and_persists_batches(tmp_path) -> None:
    db_path = tmp_path / "pipeline.db"
    storage = StorageManager(str(db_path))
    await storage.initialize()

    queue: asyncio.Queue[list[dict]] = asyncio.Queue()
    engine = ValidationEngine(default_schema())
    producer = DataProducer(
        queue,
        default_schema(),
        records_per_second=1000,
        batch_size=3,
        error_rate=0.0,
    )
    consumer = DataConsumer(queue, engine, storage)

    producer_task = asyncio.create_task(producer.run(max_batches=1))
    consumer_task = asyncio.create_task(consumer.run(max_batches=1))
    await asyncio.gather(producer_task, consumer_task)

    stats = await storage.get_stats(window_hours=24)
    assert stats["total_records"] == 3
