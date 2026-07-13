from __future__ import annotations

from app.database import MySQLConnection


class RecordingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def execute(self, *args):
        self.calls.append(args)


class RecordingRawConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> RecordingCursor:
        return self._cursor


def mysql_connection(cursor: RecordingCursor) -> MySQLConnection:
    connection = MySQLConnection.__new__(MySQLConnection)
    connection.raw = RecordingRawConnection(cursor)
    return connection


def test_mysql_execute_does_not_format_literal_percent_without_params():
    cursor = RecordingCursor()

    mysql_connection(cursor).execute("DELETE FROM orders WHERE user_id LIKE 'test-%'")

    assert cursor.calls == [("DELETE FROM orders WHERE user_id LIKE 'test-%'",)]


def test_mysql_execute_translates_bound_placeholders_with_params():
    cursor = RecordingCursor()

    mysql_connection(cursor).execute(
        "DELETE FROM orders WHERE user_id LIKE ?",
        ("test-%",),
    )

    assert cursor.calls == [("DELETE FROM orders WHERE user_id LIKE %s", ("test-%",))]
