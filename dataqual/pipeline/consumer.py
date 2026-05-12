from __future__ import annotations

import asyncio
from typing import Any

from dataqual.engine import ValidationEngine
from dataqual.storage import StorageManager


class DataConsumer:
    # keep queue engine and storage together
    def __init__(
        self,
        queue: asyncio.Queue[list[dict[str, Any]]],
        engine: ValidationEngine,
        storage: StorageManager,
    ):
        self.queue = queue
        self.engine = engine
        self.storage = storage
        self._running = True

    # pull batches then validate and save
    async def run(self, max_batches: int | None = None) -> None:
        processed = 0
        while self._running and (max_batches is None or processed < max_batches):
            batch = await self.queue.get()
            try:
                run = await self.engine.validate_batch(batch, triggered_by="pipeline")
                await self.storage.save_run(run)
                processed += 1
            finally:
                self.queue.task_done()

    # flip the loop off
    def stop(self) -> None:
        self._running = False
