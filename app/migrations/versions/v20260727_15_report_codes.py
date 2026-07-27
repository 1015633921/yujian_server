from __future__ import annotations


VERSION = "20260727_15_report_codes"


def _day_key(created_at: object) -> str:
    digits = "".join(char for char in str(created_at or "") if char.isdigit())
    return digits[:8] if len(digits) >= 8 else "00000000"


def _sqlite_columns(connection) -> set[str]:
    return {row["name"] for row in connection.execute("PRAGMA table_info(report_snapshots)").fetchall()}


def _mysql_columns(connection, database: str) -> set[str]:
    return {
        row["COLUMN_NAME"]
        for row in connection.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'report_snapshots'",
            (database,),
        ).fetchall()
    }


def _mysql_indexes(connection, database: str) -> set[str]:
    return {
        row["INDEX_NAME"]
        for row in connection.execute(
            "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'report_snapshots'",
            (database,),
        ).fetchall()
    }


def _set_counter(connection, backend: str, day: str, sequence: int) -> None:
    if backend == "mysql":
        connection.execute(
            "INSERT INTO report_code_counters(day_key, last_sequence) VALUES (?, ?) "
            "ON DUPLICATE KEY UPDATE last_sequence=GREATEST(last_sequence, VALUES(last_sequence))",
            (day, sequence),
        )
    else:
        connection.execute(
            "INSERT INTO report_code_counters(day_key, last_sequence) VALUES (?, ?) "
            "ON CONFLICT(day_key) DO UPDATE SET last_sequence=MAX(last_sequence, excluded.last_sequence)",
            (day, sequence),
        )


def upgrade(connection, backend: str, database: str = "") -> None:
    columns = _mysql_columns(connection, database) if backend == "mysql" else _sqlite_columns(connection)
    if "report_code" not in columns:
        connection.execute("ALTER TABLE report_snapshots ADD COLUMN report_code VARCHAR(32)" if backend == "mysql" else "ALTER TABLE report_snapshots ADD COLUMN report_code TEXT")

    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS report_code_counters ("
        "day_key VARCHAR(8) PRIMARY KEY, last_sequence INT NOT NULL"
        f"){suffix}"
    )

    counters: dict[str, int] = {}
    rows = connection.execute(
        "SELECT report_id, report_code, created_at FROM report_snapshots ORDER BY created_at ASC, report_id ASC"
    ).fetchall()
    for row in rows:
        day = _day_key(row["created_at"])
        counters[day] = counters.get(day, 0) + 1
        code = str(row["report_code"] or "").strip()
        if not code:
            code = f"RPT-{day}-{counters[day]:04d}"
            connection.execute("UPDATE report_snapshots SET report_code = ? WHERE report_id = ?", (code, row["report_id"]))
    for day, sequence in counters.items():
        _set_counter(connection, backend, day, sequence)

    if backend == "mysql":
        if "ux_report_snapshots_report_code" not in _mysql_indexes(connection, database):
            connection.execute("CREATE UNIQUE INDEX ux_report_snapshots_report_code ON report_snapshots(report_code)")
    else:
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_report_snapshots_report_code ON report_snapshots(report_code)")


def downgrade(connection, backend: str, database: str = "") -> None:
    del database
    if backend == "mysql":
        connection.execute("DROP INDEX ux_report_snapshots_report_code ON report_snapshots")
        connection.execute("ALTER TABLE report_snapshots DROP COLUMN report_code")
    else:
        connection.execute("DROP INDEX IF EXISTS ux_report_snapshots_report_code")
        connection.execute("ALTER TABLE report_snapshots DROP COLUMN report_code")
    connection.execute("DROP TABLE IF EXISTS report_code_counters")
