from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any

from dataqual.models import Schema


class DataProducer:
    # keep queue settings and fake data knobs
    def __init__(
        self,
        queue: asyncio.Queue[list[dict[str, Any]]],
        schema: Schema,
        records_per_second: int = 10,
        batch_size: int = 50,
        error_rate: float = 0.1,
    ):
        self.queue = queue
        self.schema = schema
        self.records_per_second = records_per_second
        self.batch_size = batch_size
        self.error_rate = error_rate
        self._running = True
        self._id_counter = 1
        self._event_types = ["purchase", "refund", "signup", "click"]

    # push batches into the queue
    async def run(self, max_batches: int | None = None) -> None:
        produced = 0
        while self._running and (max_batches is None or produced < max_batches):
            batch = [self._generate_record() for _ in range(self.batch_size)]
            await self.queue.put(batch)
            produced += 1
            await asyncio.sleep(self.batch_size / max(self.records_per_second, 1))

    # flip the loop off
    def stop(self) -> None:
        self._running = False

    # sample {"id": 1, "user_id": 22, "event_type": "purchase", "amount": 12.5, "timestamp": "..."}
    def _generate_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "id": self._id_counter,
            "user_id": random.randint(1, 500),
            "event_type": random.choice(self._event_types),
            "amount": round(random.uniform(1, 500), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._id_counter += 1

        if random.random() >= self.error_rate:
            return record

        mutation = random.choice(["null", "type", "range", "duplicate"])
        if mutation == "null":
            target = random.choice(self.schema.get_required_fields())
            record[target] = None
        elif mutation == "type":
            target = random.choice(["id", "user_id", "amount"])
            record[target] = "bad-type"
        elif mutation == "range":
            record["amount"] = -5.0
        elif mutation == "duplicate" and self._id_counter > 2:
            record["id"] = self._id_counter - 2

        return record
