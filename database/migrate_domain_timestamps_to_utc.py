import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

from database.timezone import legacy_local_naive_to_utc_naive


DOMAIN_TIMESTAMP_COLUMNS = {
    "raw_events": ("event_time",),
    "body_metrics": ("measured_at",),
    "food_entries": ("consumed_at",),
    "activity_entries": ("recorded_at",),
    "sleep_entries": ("sleep_start", "sleep_end"),
    "workout_sessions": ("started_at",),
}
EXPECTED_PRE_MIGRATION_SHA256 = (
    "abf4f741ef8d445d8a3cf137e79830a998a7628b8166390d3c8d29979eb82631"
)


def migrate(database_path: Path) -> dict[str, int]:
    current_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
    if current_hash != EXPECTED_PRE_MIGRATION_SHA256:
        raise RuntimeError(
            "Database does not match the audited pre-migration state; "
            "migration was already applied or the database has changed."
        )

    connection = sqlite3.connect(database_path)
    migrated_counts: dict[str, int] = {}

    try:
        connection.execute("BEGIN IMMEDIATE")

        for table, columns in DOMAIN_TIMESTAMP_COLUMNS.items():
            for column in columns:
                rows = connection.execute(
                    f"SELECT id, {column} FROM {table} "
                    f"WHERE {column} IS NOT NULL"
                ).fetchall()

                for row_id, raw_value in rows:
                    local_value = datetime.fromisoformat(raw_value)
                    utc_value = legacy_local_naive_to_utc_naive(local_value)
                    connection.execute(
                        f"UPDATE {table} SET {column} = ? WHERE id = ?",
                        (utc_value.isoformat(sep=" "), row_id),
                    )

                migrated_counts[f"{table}.{column}"] = len(rows)

        integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity_result != ("ok",):
            raise RuntimeError(f"SQLite integrity check failed: {integrity_result}")

        connection.commit()
        return migrated_counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    counts = migrate(Path("fitness.db"))
    for name, count in counts.items():
        print(f"{name}: {count}")
