from __future__ import annotations


VERSION = "20260712_05_p1c_runtime_tasks"


def upgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_task_leases (
              task_name VARCHAR(100) PRIMARY KEY,
              owner_id VARCHAR(100) NOT NULL DEFAULT '',
              lease_until VARCHAR(40) NOT NULL,
              updated_at VARCHAR(40) NOT NULL,
              INDEX idx_runtime_task_leases_until (lease_until)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_task_runs (
              run_id VARCHAR(100) PRIMARY KEY,
              task_name VARCHAR(100) NOT NULL,
              owner_id VARCHAR(100) NOT NULL,
              status VARCHAR(32) NOT NULL,
              attempt_count INT NOT NULL DEFAULT 0,
              checked_count INT NOT NULL DEFAULT 0,
              failed_count INT NOT NULL DEFAULT 0,
              error_type VARCHAR(100) NOT NULL DEFAULT '',
              started_at VARCHAR(40) NOT NULL,
              finished_at VARCHAR(40),
              INDEX idx_runtime_task_runs_task_started (task_name, started_at),
              INDEX idx_runtime_task_runs_status_started (status, started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        return
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_task_leases (
          task_name TEXT PRIMARY KEY,
          owner_id TEXT NOT NULL DEFAULT '',
          lease_until TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_task_leases_until ON runtime_task_leases(lease_until)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_task_runs (
          run_id TEXT PRIMARY KEY,
          task_name TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          status TEXT NOT NULL,
          attempt_count INTEGER NOT NULL DEFAULT 0,
          checked_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          error_type TEXT NOT NULL DEFAULT '',
          started_at TEXT NOT NULL,
          finished_at TEXT
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_task_runs_task_started ON runtime_task_runs(task_name, started_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_task_runs_status_started ON runtime_task_runs(status, started_at)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute("DROP TABLE IF EXISTS runtime_task_runs")
        connection.execute("DROP TABLE IF EXISTS runtime_task_leases")
        return
    connection.execute("DROP INDEX IF EXISTS idx_runtime_task_runs_status_started")
    connection.execute("DROP INDEX IF EXISTS idx_runtime_task_runs_task_started")
    connection.execute("DROP INDEX IF EXISTS idx_runtime_task_leases_until")
    connection.execute("DROP TABLE IF EXISTS runtime_task_runs")
    connection.execute("DROP TABLE IF EXISTS runtime_task_leases")
