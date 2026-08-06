from __future__ import annotations


VERSION = "20260723_12_ai_material_annotations"


def upgrade(connection, backend: str, database: str = "") -> None:
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_material_annotations (
          annotation_id VARCHAR(80) PRIMARY KEY,
          target_id VARCHAR(80) NOT NULL,
          material_code VARCHAR(160) NOT NULL,
          top VARCHAR(40) NOT NULL DEFAULT '',
          category VARCHAR(100) NOT NULL DEFAULT '',
          series VARCHAR(160) NOT NULL DEFAULT '',
          model_id VARCHAR(100) NOT NULL,
          prompt_version VARCHAR(100) NOT NULL,
          schema_version VARCHAR(100) NOT NULL,
          input_fingerprint CHAR(64) NOT NULL,
          image_urls_json LONGTEXT NOT NULL,
          known_facts_json LONGTEXT NOT NULL,
          raw_response_json LONGTEXT NOT NULL,
          parsed_response_json LONGTEXT NOT NULL,
          reviewer_final_json LONGTEXT NOT NULL,
          status VARCHAR(30) NOT NULL,
          request_id VARCHAR(160) NOT NULL DEFAULT '',
          usage_json LONGTEXT NOT NULL,
          error_code VARCHAR(80) NOT NULL DEFAULT '',
          error_message VARCHAR(500) NOT NULL DEFAULT '',
          review_notes VARCHAR(1000) NOT NULL DEFAULT '',
          reviewer_id VARCHAR(80) NOT NULL DEFAULT '',
          reviewer_name VARCHAR(120) NOT NULL DEFAULT '',
          reviewed_at VARCHAR(40),
          source_updated_at VARCHAR(40) NOT NULL DEFAULT '',
          created_at VARCHAR(40) NOT NULL,
          updated_at VARCHAR(40) NOT NULL
        )
        """ + suffix
    )
    if backend == "mysql":
        indexes = {
            row["INDEX_NAME"]
            for row in connection.execute(
                """
                SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA=? AND TABLE_NAME='ai_material_annotations'
                """,
                (database,),
            ).fetchall()
        }
        if "idx_ai_material_status_created" not in indexes:
            connection.execute(
                "CREATE INDEX idx_ai_material_status_created "
                "ON ai_material_annotations(status, created_at)"
            )
        if "idx_ai_material_target_created" not in indexes:
            connection.execute(
                "CREATE INDEX idx_ai_material_target_created "
                "ON ai_material_annotations(target_id, created_at)"
            )
        if "idx_ai_material_fingerprint" not in indexes:
            connection.execute(
                "CREATE INDEX idx_ai_material_fingerprint "
                "ON ai_material_annotations(input_fingerprint)"
            )
        return
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_material_status_created "
        "ON ai_material_annotations(status, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_material_target_created "
        "ON ai_material_annotations(target_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_material_fingerprint "
        "ON ai_material_annotations(input_fingerprint)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute("DROP TABLE IF EXISTS ai_material_annotations")
        return
    connection.execute("DROP INDEX IF EXISTS idx_ai_material_fingerprint")
    connection.execute("DROP INDEX IF EXISTS idx_ai_material_target_created")
    connection.execute("DROP INDEX IF EXISTS idx_ai_material_status_created")
    connection.execute("DROP TABLE IF EXISTS ai_material_annotations")
