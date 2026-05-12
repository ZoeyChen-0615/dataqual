import pytest

from dataqual.engine import ValidationEngine
from dataqual.models import default_schema


@pytest.mark.asyncio
async def test_validate_batch_counts_pass_and_fail_records() -> None:
    engine = ValidationEngine(default_schema(), rule_names=["null_check", "range_check"])
    run = await engine.validate_batch(
        [
            {"id": 1, "user_id": 1, "event_type": "purchase", "amount": 10.0, "timestamp": "ts"},
            {"id": 2, "user_id": None, "event_type": "purchase", "amount": -5.0, "timestamp": "ts"},
        ]
    )
    assert run.total_records == 2
    assert run.pass_count == 1
    assert run.fail_count == 1
