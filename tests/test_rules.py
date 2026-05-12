from dataqual.models import ValidationContext, default_schema
from dataqual.rules.builtin import null_check, range_check, type_check, uniqueness_check


def test_null_check_flags_missing_required_fields() -> None:
    results = null_check(
        {"id": 1, "user_id": None, "event_type": "purchase", "amount": 10.5, "timestamp": "ts"},
        default_schema(),
        ValidationContext(record_index=0, batch_records=[]),
    )
    assert any(result.field == "user_id" and not result.passed for result in results)


def test_type_check_rejects_wrong_type() -> None:
    results = type_check(
        {"id": "bad", "user_id": 1, "event_type": "purchase", "amount": 10.5, "timestamp": "ts"},
        default_schema(),
        ValidationContext(record_index=0, batch_records=[]),
    )
    assert any(result.field == "id" and not result.passed for result in results)


def test_range_check_rejects_negative_amount() -> None:
    results = range_check(
        {"id": 1, "user_id": 2, "event_type": "purchase", "amount": -1.0, "timestamp": "ts"},
        default_schema(),
        ValidationContext(record_index=0, batch_records=[]),
    )
    assert any(result.field == "amount" and not result.passed for result in results)


def test_uniqueness_check_flags_second_duplicate() -> None:
    context = ValidationContext(record_index=0, batch_records=[])
    first = uniqueness_check(
        {"id": 1, "user_id": 1, "event_type": "purchase", "amount": 10.5, "timestamp": "ts"},
        default_schema(),
        context,
    )
    second = uniqueness_check(
        {"id": 1, "user_id": 2, "event_type": "purchase", "amount": 9.5, "timestamp": "ts"},
        default_schema(),
        context,
    )
    assert all(result.passed for result in first)
    assert any(result.field == "id" and not result.passed for result in second)
