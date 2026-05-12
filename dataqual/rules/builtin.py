from __future__ import annotations

from typing import Any

from dataqual.models import RuleResult, Schema, ValidationContext
from dataqual.rules.registry import RuleRegistry


@RuleRegistry.register(
    name="null_check",
    severity="error",
    description="Checks for null or missing values in required fields.",
)
# one record can fail on a few missing fields
def null_check(
    record: dict[str, Any], schema: Schema, context: ValidationContext
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for field in schema.fields:
        value = record.get(field.name)
        missing = value is None or (isinstance(value, str) and value.strip() == "")
        if field.required and missing:
            results.append(
                RuleResult(
                    rule_name="null_check",
                    passed=False,
                    severity="error",
                    field=field.name,
                    message=f"Required field '{field.name}' is missing or null.",
                )
            )
    if results:
        return results
    return [
        RuleResult(
            rule_name="null_check",
            passed=True,
            severity="error",
            message="All required fields are present.",
        )
    ]


@RuleRegistry.register(
    name="type_check",
    severity="error",
    description="Validates field types match the schema.",
)
# catch wrong python types
def type_check(
    record: dict[str, Any], schema: Schema, context: ValidationContext
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for field in schema.fields:
        value = record.get(field.name)
        if value is None:
            continue
        if field.field_type is float and isinstance(value, int):
            continue
        if not isinstance(value, field.field_type):
            results.append(
                RuleResult(
                    rule_name="type_check",
                    passed=False,
                    severity="error",
                    field=field.name,
                    message=(
                        f"Field '{field.name}' expected {field.field_type.__name__}, "
                        f"got {type(value).__name__}."
                    ),
                )
            )
    if results:
        return results
    return [
        RuleResult(
            rule_name="type_check",
            passed=True,
            severity="error",
            message="All field types match the schema.",
        )
    ]


@RuleRegistry.register(
    name="range_check",
    severity="warning",
    description="Checks numeric fields are within expected ranges.",
)
# check min and max
def range_check(
    record: dict[str, Any], schema: Schema, context: ValidationContext
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for field in schema.numeric_fields():
        value = record.get(field.name)
        if not isinstance(value, (int, float)):
            continue
        if field.min_value is not None and value < field.min_value:
            results.append(
                RuleResult(
                    rule_name="range_check",
                    passed=False,
                    severity="warning",
                    field=field.name,
                    message=f"Field '{field.name}' below minimum of {field.min_value}.",
                )
            )
        if field.max_value is not None and value > field.max_value:
            results.append(
                RuleResult(
                    rule_name="range_check",
                    passed=False,
                    severity="warning",
                    field=field.name,
                    message=f"Field '{field.name}' above maximum of {field.max_value}.",
                )
            )
    if results:
        return results
    return [
        RuleResult(
            rule_name="range_check",
            passed=True,
            severity="warning",
            message="All numeric values are within range.",
        )
    ]


@RuleRegistry.register(
    name="uniqueness_check",
    severity="error",
    description="Detects duplicate IDs within a batch.",
)
# batch level duplicate check
def uniqueness_check(
    record: dict[str, Any], schema: Schema, context: ValidationContext
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for field in schema.unique_fields():
        value = record.get(field.name)
        if value is None:
            continue
        seen = context.seen_unique_values.setdefault(field.name, set())
        if value in seen:
            results.append(
                RuleResult(
                    rule_name="uniqueness_check",
                    passed=False,
                    severity="error",
                    field=field.name,
                    message=f"Duplicate value '{value}' found for unique field '{field.name}'.",
                )
            )
        seen.add(value)
    if results:
        return results
    return [
        RuleResult(
            rule_name="uniqueness_check",
            passed=True,
            severity="error",
            message="All unique fields are unique within the batch.",
        )
    ]


@RuleRegistry.register(
    name="anomaly_check",
    severity="warning",
    description="Flags statistically unusual numeric values using z-score.",
)
# rough outlier flag
def anomaly_check(
    record: dict[str, Any], schema: Schema, context: ValidationContext
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for field in schema.numeric_fields():
        stats = context.numeric_stats.get(field.name)
        value = record.get(field.name)
        if stats is None or not isinstance(value, (int, float)):
            continue
        avg, stddev = stats
        if stddev == 0:
            continue
        z_score = abs((float(value) - avg) / stddev)
        if z_score >= 3:
            results.append(
                RuleResult(
                    rule_name="anomaly_check",
                    passed=False,
                    severity="warning",
                    field=field.name,
                    message=f"Field '{field.name}' has anomalous z-score {z_score:.2f}.",
                )
            )
    if results:
        return results
    return [
        RuleResult(
            rule_name="anomaly_check",
            passed=True,
            severity="warning",
            message="No anomalies detected.",
        )
    ]
