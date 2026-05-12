from datetime import datetime, timezone

import pytest

from dataqual.models import RecordValidationResult, RuleResult, new_run
from dataqual.storage import StorageManager


@pytest.mark.asyncio
async def test_storage_saves_and_queries_results(tmp_path) -> None:
    db_path = tmp_path / "dataqual.db"
    storage = StorageManager(str(db_path))
    await storage.initialize()

    run = new_run(
        triggered_by="manual",
        records=[
            RecordValidationResult(
                record_index=0,
                results=[
                    RuleResult(
                        rule_name="null_check",
                        passed=False,
                        severity="error",
                        field="user_id",
                        message="missing",
                    )
                ],
            )
        ],
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )

    await storage.save_run(run)
    results = await storage.get_results(rule="null_check")
    stats = await storage.get_stats(window_hours=24)
    fetched_run = await storage.get_run(run.run_id)

    assert len(results) == 1
    assert results[0]["field"] == "user_id"
    assert stats["failures_by_rule"]["null_check"] == 1
    assert fetched_run is not None
    assert fetched_run["id"] == run.run_id
