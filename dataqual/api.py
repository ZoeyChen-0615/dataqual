from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from dataqual.engine import ValidationEngine
from dataqual.models import default_schema
from dataqual.rules import RuleRegistry
from dataqual.storage import StorageManager


class ValidateRequest(BaseModel):
    data: list[dict[str, Any]] = Field(default_factory=list)


# parse date filters from query params
def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


# turn 24h into 24
def _parse_window(window: str) -> int:
    if not window.endswith("h"):
        raise HTTPException(status_code=400, detail="Window must use the form '<hours>h'.")
    try:
        hours = int(window[:-1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Window hours must be an integer.") from exc
    if hours <= 0:
        raise HTTPException(status_code=400, detail="Window must be greater than zero.")
    return hours


# build one app with shared objects
def create_app(
    *,
    storage: StorageManager | None = None,
    engine: ValidationEngine | None = None,
    pipeline_running: bool = False,
) -> FastAPI:
    shared_storage = storage or StorageManager()
    shared_engine = engine or ValidationEngine(default_schema())

    @asynccontextmanager
    # startup setup
    async def lifespan(app: FastAPI) -> Any:
        await shared_storage.initialize()
        app.state.storage = shared_storage
        app.state.engine = shared_engine
        app.state.pipeline_running = pipeline_running
        yield

    app = FastAPI(title="DataQual", lifespan=lifespan)

    @app.get("/health")
    # sample {"status": "ok", "pipeline_running": false}
    async def health() -> dict[str, Any]:
        return {"status": "ok", "pipeline_running": app.state.pipeline_running}

    @app.get("/rules")
    # sample [{"name": "null_check", "severity": "error"}]
    async def list_rules() -> list[dict[str, str]]:
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity,
            }
            for rule in RuleRegistry.get_all_rules()
        ]

    @app.post("/validate")
    # sample {"run_id": "...", "results": [...]}
    async def manual_validate(payload: ValidateRequest) -> dict[str, Any]:
        run = await app.state.engine.validate_batch(payload.data, triggered_by="manual")
        await app.state.storage.save_run(run)
        return {"run_id": run.run_id, "results": run.to_dict()["results"]}

    @app.get("/results")
    # filtered history rows
    async def query_results(
        rule: str | None = None,
        severity: str | None = None,
        passed: bool | None = None,
        from_dt: str | None = Query(default=None, alias="from"),
        to_dt: str | None = Query(default=None, alias="to"),
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = await app.state.storage.get_results(
            rule=rule,
            severity=severity,
            passed=passed,
            from_dt=_parse_datetime(from_dt),
            to_dt=_parse_datetime(to_dt),
        )
        return results

    @app.get("/results/{run_id}")
    # one run with nested results
    async def get_run(run_id: str) -> dict[str, Any]:
        run = await app.state.storage.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        response: dict[str, Any] = run
        return response

    @app.get("/stats")
    # sample {"total_records": 20, "pass_rate": 0.95}
    async def get_stats(window: str = "24h") -> dict[str, Any]:
        hours = _parse_window(window)
        stats: dict[str, Any] = await app.state.storage.get_stats(window_hours=hours)
        return stats

    return app


app = create_app()
