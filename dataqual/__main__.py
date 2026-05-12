from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any

import click
import uvicorn
from fastapi import FastAPI

from dataqual.api import create_app
from dataqual.engine import ValidationEngine
from dataqual.models import default_schema
from dataqual.pipeline.consumer import DataConsumer
from dataqual.pipeline.producer import DataProducer
from dataqual.rules import RuleRegistry
from dataqual.storage import StorageManager


# turn csv text into python values
def _coerce_csv_value(value: str) -> Any:
    if value == "":
        return None
    for caster in (int, float):
        try:
            return caster(value)
        except ValueError:
            continue
    return value


# sample [{"id": 1, "amount": 10.5}]
def _load_csv_records(file_path: Path) -> list[dict[str, Any]]:
    with file_path.open(newline="", encoding="utf-8") as handle:
        return [
            {key: _coerce_csv_value(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


# boot uvicorn
async def _serve_app(app: FastAPI, host: str, port: int) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    await server.serve()


# run api plus producer and consumer
async def _run_start(
    db_path: str, host: str, port: int, records_per_second: int, batch_size: int, error_rate: float
) -> None:
    schema = default_schema()
    storage = StorageManager(db_path)
    await storage.initialize()
    engine = ValidationEngine(schema)
    queue: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue()
    producer = DataProducer(
        queue,
        schema,
        records_per_second=records_per_second,
        batch_size=batch_size,
        error_rate=error_rate,
    )
    consumer = DataConsumer(queue, engine, storage)
    app = create_app(storage=storage, engine=engine, pipeline_running=True)

    producer_task = asyncio.create_task(producer.run(), name="dataqual-producer")
    consumer_task = asyncio.create_task(consumer.run(), name="dataqual-consumer")
    try:
        await _serve_app(app, host, port)
    finally:
        producer.stop()
        consumer.stop()
        producer_task.cancel()
        consumer_task.cancel()
        await asyncio.gather(producer_task, consumer_task, return_exceptions=True)


# run api only
async def _run_serve(db_path: str, host: str, port: int) -> None:
    storage = StorageManager(db_path)
    engine = ValidationEngine(default_schema())
    app = create_app(storage=storage, engine=engine, pipeline_running=False)
    await _serve_app(app, host, port)


# sample {"run_id": "...", "pass_count": 3}
async def _run_validate(db_path: str, file_path: Path) -> dict[str, Any]:
    storage = StorageManager(db_path)
    await storage.initialize()
    engine = ValidationEngine(default_schema())
    records = _load_csv_records(file_path)
    run = await engine.validate_batch(records, triggered_by="manual")
    await storage.save_run(run)
    return run.to_dict()


@click.group()
# cli root
def cli() -> None:
    """Data quality monitoring commands."""


@cli.command()
@click.option("--db-path", default="dataqual.db", show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--records-per-second", default=10, show_default=True, type=int)
@click.option("--batch-size", default=50, show_default=True, type=int)
@click.option("--error-rate", default=0.1, show_default=True, type=float)
# start everything
def start(
    db_path: str, host: str, port: int, records_per_second: int, batch_size: int, error_rate: float
) -> None:
    """Start the pipeline and API server together."""
    asyncio.run(
        _run_start(
            db_path=db_path,
            host=host,
            port=port,
            records_per_second=records_per_second,
            batch_size=batch_size,
            error_rate=error_rate,
        )
    )


@cli.command()
@click.option("--db-path", default="dataqual.db", show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
# serve api only
def serve(db_path: str, host: str, port: int) -> None:
    """Start only the API server."""
    asyncio.run(_run_serve(db_path=db_path, host=host, port=port))


@cli.command()
@click.option("--db-path", default="dataqual.db", show_default=True)
@click.option("--file", "file_path", required=True, type=click.Path(exists=True, path_type=Path))
# validate one csv file
def validate(db_path: str, file_path: Path) -> None:
    """Validate records from a CSV file."""
    result = asyncio.run(_run_validate(db_path=db_path, file_path=file_path))
    click.echo(json.dumps(result, indent=2))


@cli.command(name="rules")
# print registered rules
def rules_command() -> None:
    """List registered validation rules."""
    payload = [
        {
            "name": rule.name,
            "severity": rule.severity,
            "description": rule.description,
        }
        for rule in RuleRegistry.get_all_rules()
    ]
    click.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    cli()
