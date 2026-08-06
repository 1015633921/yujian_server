from __future__ import annotations


VERSION = "20260727_14_custom_design_service"


def upgrade(connection, backend: str, database: str = "") -> None:
    del database
    text = "LONGTEXT" if backend == "mysql" else "TEXT"
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(f"""CREATE TABLE IF NOT EXISTS custom_design_requests (
      request_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL,
      report_id VARCHAR(80) NOT NULL, report_version INT NOT NULL, request_json {text} NOT NULL,
      status VARCHAR(40) NOT NULL, first_draft_due_at VARCHAR(40), created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL, proposed_at VARCHAR(40), confirmed_at VARCHAR(40)
    ){suffix}""")
    connection.execute(f"""CREATE TABLE IF NOT EXISTS custom_design_proposals (
      proposal_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL, proposal_version INT NOT NULL,
      title VARCHAR(160) NOT NULL, description {text} NOT NULL, image_urls_json {text} NOT NULL,
      status VARCHAR(20) NOT NULL, created_by VARCHAR(100) NOT NULL, created_at VARCHAR(40) NOT NULL,
      UNIQUE(request_id, proposal_version)
    ){suffix}""")
    connection.execute(f"""CREATE TABLE IF NOT EXISTS custom_design_events (
      event_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL, event_type VARCHAR(40) NOT NULL,
      from_status VARCHAR(40) NOT NULL DEFAULT '', to_status VARCHAR(40) NOT NULL DEFAULT '', actor_type VARCHAR(20) NOT NULL,
      actor_id VARCHAR(100) NOT NULL, note VARCHAR(500) NOT NULL DEFAULT '', created_at VARCHAR(40) NOT NULL
    ){suffix}""")
    for name, table, columns in (
        ("idx_custom_design_requests_user_created", "custom_design_requests", "user_id, created_at"),
        ("idx_custom_design_requests_status_created", "custom_design_requests", "status, created_at"),
        ("idx_custom_design_proposals_request", "custom_design_proposals", "request_id, proposal_version"),
        ("idx_custom_design_events_request_created", "custom_design_events", "request_id, created_at"),
    ):
        if backend == "mysql":
            connection.execute(f"CREATE INDEX {name} ON {table} ({columns})")
        else:
            connection.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def downgrade(connection, backend: str, database: str = "") -> None:
    del backend, database
    connection.execute("DROP TABLE IF EXISTS custom_design_events")
    connection.execute("DROP TABLE IF EXISTS custom_design_proposals")
    connection.execute("DROP TABLE IF EXISTS custom_design_requests")
