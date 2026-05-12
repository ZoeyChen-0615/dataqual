# DataQual

DataQual is a real-time data quality monitoring system in Python. It simulates a stream of event records, validates those records with a rule system, stores validation history in SQLite, and exposes a FastAPI API for querying results and statistics.

The project is built as a small end-to-end system rather than a single script. It has a running pipeline, validation rules, persistent storage, a web API, and CLI commands for starting the system or running manual validation.

## Demo

In a demo, I start the full system with one command. After that:

- the producer keeps generating fake event data
- the consumer validates each batch
- the validation results are written into SQLite
- I can open API endpoints like `/health`, `/rules`, `/results`, and `/stats`
- I can also run a manual validation on a CSV file and compare that result with the automatically generated data

So the demo shows both continuous validation and one-off validation.

## Features

- async producer-consumer pipeline built with `asyncio`
- decorator-based validation rule registry
- batch validation engine
- SQLite persistence through `aiosqlite`
- FastAPI API for health checks, rules, results, and stats
- CLI commands for running the system or validating a file

## Project Structure

```text
dataqual_project/
  dataqual/
    __init__.py
    __main__.py
    api.py
    engine.py
    models.py
    storage.py
    pipeline/
      consumer.py
      producer.py
    rules/
      __init__.py
      builtin.py
      registry.py
  tests/
    test_api.py
    test_engine.py
    test_pipeline.py
    test_rules.py
    test_storage.py
  pyproject.toml
  README.md
```

## Architecture

At a high level the system works like this:

1. `DataProducer` generates synthetic event records in batches
2. those batches are pushed into an `asyncio.Queue`
3. `DataConsumer` pulls batches from the queue
4. `ValidationEngine` runs validation rules on each record
5. `StorageManager` writes run summaries and rule results into SQLite
6. the FastAPI app exposes endpoints for querying rules, results, and stats

## File Overview

### `dataqual/models.py`

Defines the main data structures used across the project.

- schema definitions
- rule result objects
- record-level result objects
- run-level result objects
- helper functions for default schema and numeric statistics

### `dataqual/rules/registry.py`

Handles rule registration.

- stores all registered rules
- provides the decorator used to register a new rule
- lets the engine fetch rules by name or list all rules

### `dataqual/rules/builtin.py`

Contains the built-in validation rules.

Current rules include:

- null check
- type check
- range check
- uniqueness check
- anomaly check

### `dataqual/engine.py`

Runs the validation process.

Important jobs:

- choose which rules to run
- validate a whole batch
- validate one record
- assemble the final validation result

### `dataqual/pipeline/producer.py`

Simulates incoming data.

Important jobs:

- generate fake records
- inject occasional bad data
- push batches into the queue

### `dataqual/pipeline/consumer.py`

Processes incoming batches.

Important jobs:

- read from the queue
- send data to the validation engine
- save results to storage

### `dataqual/storage.py`

Owns all database work.

Important jobs:

- create tables
- save validation runs
- save detailed rule results
- query historical results
- compute aggregate stats

### `dataqual/api.py`

Defines the FastAPI app and the HTTP endpoints.

### `dataqual/__main__.py`

Defines the CLI commands:

- `start`
- `serve`
- `validate`
- `rules`

## Data Model

The SQLite database uses two tables.

### `validation_runs`

Stores one row per validation batch:

- `id`
- `triggered_by`
- `started_at`
- `finished_at`
- `total_records`
- `pass_count`
- `fail_count`

### `validation_results`

Stores one row per rule result:

- `id`
- `run_id`
- `record_index`
- `rule_name`
- `passed`
- `severity`
- `field`
- `message`
- `created_at`

## Setup

From the project root:

```bash
uv sync --extra dev
```

## Running The Project

### Start full system

Runs both the API server and the async producer-consumer pipeline:

```bash
uv run python -m dataqual start
```

After startup, the service is available at:

```text
http://127.0.0.1:8000
```

### Start API only

Runs only the API server:

```bash
uv run python -m dataqual serve
```

### Validate a CSV file

Runs one-off validation against local CSV input:

```bash
uv run python -m dataqual validate --file sample.csv
```

If you only want to test different values, edit `sample.csv`. If you want a different field structure, also update the project schema in `dataqual/models.py` and any related validation rules.

### List rules in the terminal

```bash
uv run python -m dataqual rules
```

## Example API Usage

Once the server is running:

### Health check

```bash
curl http://127.0.0.1:8000/health
```
![health](image.png)
Example response:

```json
{"status":"ok","pipeline_running":true}
```

### List rules

```bash
curl http://127.0.0.1:8000/rules
```

### View all results

This returns historical results stored in the database, including older generated data if the same `dataqual.db` file is reused.

```bash
curl http://127.0.0.1:8000/results
```

### View only failures

Use `passed=false` if you only want failed rule results instead of the full history.

```bash
curl "http://127.0.0.1:8000/results?passed=false"
```

### View stats

```bash
curl "http://127.0.0.1:8000/stats?window=24h"
```

### Trigger manual validation

```bash
curl -X POST http://127.0.0.1:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {
        "id": 1,
        "user_id": null,
        "event_type": "purchase",
        "amount": -5,
        "timestamp": "2026-05-12T10:00:00+00:00"
      }
    ]
  }'
```

## Testing

Run tests:

```bash
uv run --extra dev pytest -q
```

Run Ruff:

```bash
uv run --extra dev ruff check dataqual tests
```



