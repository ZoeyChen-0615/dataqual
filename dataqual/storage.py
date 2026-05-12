from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from dataqual.models import ValidationRunResult


class StorageManager:
    # remember db file path
    def __init__(self, db_path: str = "dataqual.db"):
        self.db_path = str(Path(db_path))

    # create tables if missing
    async def initialize(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS validation_runs (
                    id TEXT PRIMARY KEY,
                    triggered_by TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    total_records INTEGER NOT NULL,
                    pass_count INTEGER NOT NULL,
                    fail_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    record_index INTEGER NOT NULL,
                    rule_name TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    field TEXT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES validation_runs(id)
                );
                """
            )
            await db.commit()

    # write one full run and all rule rows
    async def save_run(self, run: ValidationRunResult) -> None:
        created_at = run.finished_at.isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO validation_runs (
                    id, triggered_by, started_at, finished_at,
                    total_records, pass_count, fail_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.triggered_by,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.total_records,
                    run.pass_count,
                    run.fail_count,
                ),
            )
            await db.executemany(
                """
                INSERT INTO validation_results (
                    run_id, record_index, rule_name, passed,
                    severity, field, message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run.run_id,
                        row["record_index"],
                        row["rule_name"],
                        int(row["passed"]),
                        row["severity"],
                        row["field"],
                        row["message"],
                        created_at,
                    )
                    for row in run.flatten_results()
                ],
            )
            await db.commit()

    # sample [{"rule_name": "null_check", "field": "user_id"}]
    async def get_results(
        self,
        rule: str | None = None,
        severity: str | None = None,
        passed: bool | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if rule:
            clauses.append("rule_name = ?")
            params.append(rule)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if passed is not None:
            clauses.append("passed = ?")
            params.append(int(passed))
        if from_dt:
            clauses.append("created_at >= ?")
            params.append(from_dt.isoformat())
        if to_dt:
            clauses.append("created_at <= ?")
            params.append(to_dt.isoformat())

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT id, run_id, record_index, rule_name, passed, severity, field, message, created_at
            FROM validation_results
            {where}
            ORDER BY created_at DESC, id DESC
        """

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # sample {"id": "...", "results": [...]}
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, triggered_by, started_at, finished_at,
                       total_records, pass_count, fail_count
                FROM validation_runs
                WHERE id = ?
                """,
                (run_id,),
            ) as cursor:
                run = await cursor.fetchone()
            if run is None:
                return None
            async with db.execute(
                """
                SELECT record_index, rule_name, passed, severity, field, message, created_at
                FROM validation_results
                WHERE run_id = ?
                ORDER BY record_index, id
                """,
                (run_id,),
            ) as cursor:
                results = await cursor.fetchall()
        return {**dict(run), "results": [dict(row) for row in results]}

    # sample {"total_records": 50, "pass_rate": 0.92}
    async def get_stats(self, window_hours: int = 24) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT
                    COALESCE(SUM(total_records), 0) AS total_records,
                    COALESCE(SUM(pass_count), 0) AS pass_count,
                    COALESCE(SUM(fail_count), 0) AS fail_count
                FROM validation_runs
                WHERE finished_at >= ?
                """,
                (since.isoformat(),),
            ) as cursor:
                fetched_summary = await cursor.fetchone()
            summary = (
                fetched_summary
                if fetched_summary is not None
                else {"total_records": 0, "pass_count": 0, "fail_count": 0}
            )
            async with db.execute(
                """
                SELECT rule_name, COUNT(*) AS failures
                FROM validation_results
                WHERE created_at >= ? AND passed = 0
                GROUP BY rule_name
                ORDER BY failures DESC, rule_name
                """,
                (since.isoformat(),),
            ) as cursor:
                failure_rows = await cursor.fetchall()

        total_records = int(summary["total_records"])
        pass_count = int(summary["pass_count"])
        pass_rate = (pass_count / total_records) if total_records else 0.0
        return {
            "window_hours": window_hours,
            "total_records": total_records,
            "pass_rate": round(pass_rate, 4),
            "fail_count": int(summary["fail_count"]),
            "failures_by_rule": {
                row["rule_name"]: row["failures"] for row in failure_rows
            },
        }
