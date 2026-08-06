from __future__ import annotations


VERSION = "20260806_17_custom_design_deposits"


def upgrade(connection, backend: str, database: str = "") -> None:
    del database
    text = "LONGTEXT" if backend == "mysql" else "TEXT"
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS custom_design_deposits (
        deposit_id VARCHAR(80) PRIMARY KEY,
        request_id VARCHAR(80) NOT NULL,
        user_id VARCHAR(100) NOT NULL,
        out_trade_no VARCHAR(64) NOT NULL,
        out_refund_no VARCHAR(64),
        amount_fee INT NOT NULL,
        currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
        status VARCHAR(40) NOT NULL,
        payment_transaction_id VARCHAR(80),
        payment_json {text} NOT NULL,
        refund_json {text} NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        paid_at VARCHAR(40),
        refund_requested_at VARCHAR(40),
        refunded_at VARCHAR(40),
        UNIQUE(request_id),
        UNIQUE(out_trade_no),
        UNIQUE(out_refund_no)
        ){suffix}"""
    )
    for name, columns in (
        ("idx_custom_design_deposits_user_created", "user_id, created_at"),
        ("idx_custom_design_deposits_status_updated", "status, updated_at"),
    ):
        if backend == "mysql":
            connection.execute(f"CREATE INDEX {name} ON custom_design_deposits ({columns})")
        else:
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON custom_design_deposits ({columns})"
            )


def downgrade(connection, backend: str, database: str = "") -> None:
    del backend, database
    connection.execute("DROP TABLE IF EXISTS custom_design_deposits")
