from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class FieldSpec:
    name: str
    field_type: type[Any]
    required: bool = True
    min_value: float | None = None
    max_value: float | None = None
    unique: bool = False


@dataclass(slots=True)
class Schema:
    fields: list[FieldSpec]

    # names like ["id", "amount"]
    def get_required_fields(self) -> list[str]:
        return [field.name for field in self.fields if field.required]

    # grab one field spec
    def get_field(self, name: str) -> FieldSpec | None:
        for field in self.fields:
            if field.name == name:
                return field
        return None

    # only unique ones
    def unique_fields(self) -> list[FieldSpec]:
        return [field for field in self.fields if field.unique]

    # only int and float fields
    def numeric_fields(self) -> list[FieldSpec]:
        return [
            field
            for field in self.fields
            if field.field_type in (int, float)
        ]





@dataclass(slots=True)
class ValidationContext:
    record_index: int
    batch_records: list[dict[str, Any]]
    seen_unique_values: dict[str, set[Any]] = field(default_factory=dict)
    numeric_stats: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(slots=True)
class RuleResult:
    rule_name: str
    passed: bool
    severity: str
    field: str | None = None
    message: str = ""

    # sample {"record_index": 0, "rule_name": "null_check", "passed": False}
    def to_dict(self, *, record_index: int) -> dict[str, Any]:
        return {
            "record_index": record_index,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }
    
@dataclass(slots=True)
class RecordValidationResult:
    record_index: int
    results: list[RuleResult]

    @property
    # all rules passed
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    # sample {"record_index": 0, "passed": True, "results": [...]}
    def to_dict(self) -> dict[str, Any]:
        return {
            "record_index": self.record_index,
            "passed": self.passed,
            "results": [
                result.to_dict(record_index=self.record_index) for result in self.results
            ],
        }


@dataclass(slots=True)
class ValidationRunResult:
    run_id: str
    triggered_by: str
    started_at: datetime
    finished_at: datetime
    total_records: int
    pass_count: int
    fail_count: int
    records: list[RecordValidationResult]

    # flat rows for sqlite
    def flatten_results(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for record in self.records:
            for result in record.results:
                rows.append(result.to_dict(record_index=record.record_index))
        return rows

    # sample {"run_id": "...", "results": [...]}
    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "triggered_by": self.triggered_by,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "total_records": self.total_records,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "results": [record.to_dict() for record in self.records],
        }


# utc timestamp helper
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# sample {"amount": (11.0, 0.8)}
def build_numeric_stats(
    records: list[dict[str, Any]], schema: Schema
) -> dict[str, tuple[float, float]]:
    stats: dict[str, tuple[float, float]] = {}
    for field_spec in schema.numeric_fields():
        values = [
            float(value)
            for record in records
            if isinstance((value := record.get(field_spec.name)), (int, float))
        ]
        if len(values) < 2:
            continue
        stats[field_spec.name] = (mean(values), pstdev(values))
    return stats


# default input shape
def default_schema() -> Schema:
    return Schema(
        fields=[
            FieldSpec(name="id", field_type=int, required=True, unique=True, min_value=1),
            FieldSpec(name="user_id", field_type=int, required=True, min_value=1),
            FieldSpec(name="event_type", field_type=str, required=True),
            FieldSpec(
                name="amount",
                field_type=float,
                required=True,
                min_value=0.0,
                max_value=10_000.0,
            ),
            FieldSpec(name="timestamp", field_type=str, required=True),
        ]
    )


# bundle one validation run
def new_run(
    *,
    triggered_by: str,
    records: list[RecordValidationResult],
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ValidationRunResult:
    started = started_at or utc_now()
    finished = finished_at or utc_now()
    total = len(records)
    passed = sum(1 for record in records if record.passed)
    failed = total - passed
    return ValidationRunResult(
        run_id=str(uuid4()),
        triggered_by=triggered_by,
        started_at=started,
        finished_at=finished,
        total_records=total,
        pass_count=passed,
        fail_count=failed,
        records=records,
    )
