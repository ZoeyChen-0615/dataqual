# DataQual

Real-time data quality monitoring system built from the M2 architecture plan.

## Commands

```bash
uv run dataqual start
uv run dataqual serve
uv run dataqual validate --file sample.csv
uv run dataqual rules
```

## API

- `GET /health`
- `GET /rules`
- `POST /validate`
- `GET /results`
- `GET /results/{run_id}`
- `GET /stats`
