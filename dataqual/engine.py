from __future__ import annotations

from typing import Any

from dataqual.models import (
    RecordValidationResult,
    Schema,
    ValidationContext,
    ValidationRunResult,
    build_numeric_stats,
    new_run,
    utc_now,
)
from dataqual.rules import RuleRegistry


class ValidationEngine:
    # pick schema and active rules
    def __init__(self, schema: Schema, rule_names: list[str] | None = None):
        self.schema = schema
        selected_names = rule_names or [entry.name for entry in RuleRegistry.get_all_rules()]
        self.rules = []
        for rule_name in selected_names:
            rule = RuleRegistry.get_rule(rule_name)
            if rule is None:
                raise ValueError(f"Unknown rule: {rule_name}")
            self.rules.append(rule)

    # sample output has run_id pass_count fail_count
    async def validate_batch(
        self, records: list[dict[str, Any]], *, triggered_by: str = "pipeline"
    ) -> ValidationRunResult:
        started_at = utc_now()
        numeric_stats = build_numeric_stats(records, self.schema)
        seen_unique_values: dict[str, set[Any]] = {}
        record_results: list[RecordValidationResult] = []

        for index, record in enumerate(records):
            context = ValidationContext(
                record_index=index,
                batch_records=records,
                seen_unique_values=seen_unique_values,
                numeric_stats=numeric_stats,
            )
            results = await self.validate_record(record, context=context)
            record_results.append(RecordValidationResult(record_index=index, results=results))

        return new_run(
            triggered_by=triggered_by,
            records=record_results,
            started_at=started_at,
            finished_at=utc_now(),
        )

    # run every selected rule on one record
    async def validate_record(
        self, record: dict[str, Any], *, context: ValidationContext | None = None
    ) -> list[Any]:
        active_context = context or ValidationContext(
            record_index=0,
            batch_records=[record],
        )
        results = []
        for rule in self.rules:
            results.extend(rule.func(record, self.schema, active_context))
        return results
