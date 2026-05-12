import pytest
from httpx import ASGITransport, AsyncClient

from dataqual.api import create_app
from dataqual.engine import ValidationEngine
from dataqual.models import default_schema
from dataqual.storage import StorageManager


@pytest.mark.asyncio
async def test_api_manual_validate_and_fetch_results(tmp_path) -> None:
    storage = StorageManager(str(tmp_path / "api.db"))
    app = create_app(storage=storage, engine=ValidationEngine(default_schema()))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with app.router.lifespan_context(app):
            health = await client.get("/health")
            assert health.status_code == 200

            response = await client.post(
                "/validate",
                json={
                    "data": [
                        {
                            "id": 1,
                            "user_id": None,
                            "event_type": "purchase",
                            "amount": -1.0,
                            "timestamp": "ts",
                        }
                    ]
                },
            )
            assert response.status_code == 200
            payload = response.json()

            run_response = await client.get(f"/results/{payload['run_id']}")
            failed_results_response = await client.get("/results?passed=false")
            passed_results_response = await client.get("/results?passed=true")
            stats_response = await client.get("/stats?window=24h")

    assert run_response.status_code == 200
    assert failed_results_response.status_code == 200
    assert passed_results_response.status_code == 200
    assert all(row["passed"] == 0 for row in failed_results_response.json())
    assert all(row["passed"] == 1 for row in passed_results_response.json())
    assert stats_response.status_code == 200
    assert stats_response.json()["total_records"] == 1
