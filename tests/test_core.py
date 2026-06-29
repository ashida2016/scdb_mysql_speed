"""SCDBMySQLSpeed 主类的单元测试（使用 mock）。"""

import csv
import io
import json
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

from scdb_mysql_speed import SCDBMySQLMeta, SCDBMySQLSpeed
from scdb_mysql_speed.exceptions import SCDBQueryError, SCDBTransactionError


# ─── 测试辅助 ────────────────────────────────────────────────────


def _make_meta() -> SCDBMySQLMeta:
    return SCDBMySQLMeta(
        host="localhost", user="root", password="", database="test",
        pool_size=1, pool_max_overflow=0,
    )


@contextmanager
def _mock_pool_connection(mock_conn):
    """为 ConnectionPool.get_connection 返回 mock 连接的辅助上下文管理器。"""
    yield mock_conn


def _create_db_with_mock_pool(mock_conn):
    """创建 SCDBMySQLSpeed 并替换其连接池为 mock。"""
    with patch("scdb_mysql_speed.core.ConnectionPool"):
        db = SCDBMySQLSpeed(_make_meta())

    # 替换 get_connection 返回 mock 连接
    db._pool = MagicMock()
    db._pool.get_connection.return_value = _mock_pool_connection(mock_conn)
    return db


# ─── 连接测试 ────────────────────────────────────────────────────


class TestTestConnection:
    """测试 test_connection 方法。"""

    def test_returns_true_on_success(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        assert db.test_connection() is True

    def test_returns_false_on_failure(self) -> None:
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("boom")

        db = _create_db_with_mock_pool(mock_conn)
        assert db.test_connection() is False


# ─── fetch_all 测试 ──────────────────────────────────────────────


class TestFetchAll:
    """测试 fetch_all 方法。"""

    def test_tuple_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ((1, "alice"), (2, "bob"))
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="tuple")

        assert result == ((1, "alice"), (2, "bob"))
        mock_cursor.execute.assert_called_once_with("SELECT * FROM users", None)

    def test_dict_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
            {"id": 2, "name": "bob"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="dict")

        assert result == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]

    def test_json_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="json")

        parsed = json.loads(result)
        assert parsed == [{"id": 1, "name": "alice"}]

    def test_dataframe_format(self) -> None:
        pytest.importorskip("pandas")
        import pandas as pd

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
            {"id": 2, "name": "bob"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="df")

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["id", "name"]
        assert len(result) == 2

    def test_xml_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
            {"id": 2, "name": "bob"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="xml")

        assert isinstance(result, str)
        root = ET.fromstring(result)
        assert root.tag == "results"
        rows = root.findall("row")
        assert len(rows) == 2
        assert rows[0].find("name").text == "alice"
        assert rows[1].find("id").text == "2"

    def test_yaml_format(self) -> None:
        yaml = pytest.importorskip("yaml")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="yaml")

        assert isinstance(result, str)
        parsed = yaml.safe_load(result)
        assert parsed == [{"id": 1, "name": "alice"}]

    def test_csv_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alice"},
            {"id": 2, "name": "bob"},
        ]
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM users", result_format="csv")

        assert isinstance(result, str)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "alice"
        assert rows[1]["id"] == "2"

    def test_with_params(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ((1, "alice"),)
        mock_cursor.description = (("id", None), ("name", None))
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        db.fetch_all("SELECT * FROM users WHERE id=%s", params=(1,))

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users WHERE id=%s", (1,)
        )

    def test_invalid_result_format_raises(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ()
        mock_cursor.description = ()
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        with pytest.raises(ValueError, match="不支持"):
            db.fetch_all("SELECT 1", result_format="html")  # type: ignore[arg-type]

    def test_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ()
        mock_cursor.description = (("id", None),)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_all("SELECT * FROM empty_table")
        assert result == ()


# ─── fetch_page 测试 ─────────────────────────────────────────────


class TestFetchPage:
    """测试 fetch_page 分页方法。"""

    def test_page_1(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ((1,), (2,))
        mock_cursor.description = (("id", None),)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        db.fetch_page("SELECT * FROM users", page=1, page_size=2)

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users LIMIT 0, 2", None
        )

    def test_page_3(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ()
        mock_cursor.description = (("id", None),)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        db.fetch_page("SELECT * FROM users", page=3, page_size=10)

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users LIMIT 20, 10", None
        )

    def test_strips_trailing_semicolon(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = ()
        mock_cursor.description = (("id", None),)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        db.fetch_page("SELECT * FROM users;", page=1, page_size=5)

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users LIMIT 0, 5", None
        )

    def test_invalid_page_raises(self) -> None:
        db = _create_db_with_mock_pool(MagicMock())
        with pytest.raises(ValueError, match="page 必须"):
            db.fetch_page("SELECT 1", page=0)

    def test_invalid_page_size_raises(self) -> None:
        db = _create_db_with_mock_pool(MagicMock())
        with pytest.raises(ValueError, match="page_size 必须"):
            db.fetch_page("SELECT 1", page_size=0)

    def test_page_with_result_format(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1}]
        mock_cursor.description = (("id", None),)
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.fetch_page(
            "SELECT * FROM users", page=1, page_size=5, result_format="dict"
        )
        assert result == [{"id": 1}]


# ─── execute 测试 ────────────────────────────────────────────────


class TestExecute:
    """测试 execute 单条增删改。"""

    def test_returns_affected_rows(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.execute("INSERT INTO users (name) VALUES (%s)", ("alice",))

        assert result == 1
        mock_conn.autocommit.assert_called_with(False)
        mock_conn.commit.assert_called_once()
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO users (name) VALUES (%s)", ("alice",)
        )

    def test_rollback_on_error(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("constraint violation")
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)

        with pytest.raises(Exception, match="constraint"):
            db.execute("INSERT INTO users (name) VALUES (%s)", ("duplicate",))

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


# ─── execute_many 测试 ───────────────────────────────────────────


class TestExecuteMany:
    """测试 execute_many 批量操作。"""

    def test_returns_affected_rows(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)
        result = db.execute_many(
            "INSERT INTO users (name) VALUES (%s)",
            [("a",), ("b",), ("c",)],
        )

        assert result == 3
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_empty_params_returns_zero(self) -> None:
        db = _create_db_with_mock_pool(MagicMock())
        assert db.execute_many("INSERT INTO t (x) VALUES (%s)", []) == 0
        assert db.execute_many("INSERT INTO t (x) VALUES (%s)", None) == 0

    def test_rollback_on_error(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.executemany.side_effect = Exception("batch error")
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)

        with pytest.raises(Exception, match="batch"):
            db.execute_many(
                "INSERT INTO t (x) VALUES (%s)", [("a",), ("b",)]
            )

        mock_conn.rollback.assert_called_once()


# ─── transaction 测试 ────────────────────────────────────────────


class TestTransaction:
    """测试事务上下文管理器。"""

    def test_commit_on_success(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)

        with db.transaction() as cursor:
            cursor.execute("INSERT INTO t1 VALUES (%s)", (1,))
            cursor.execute("UPDATE t2 SET x=1")

        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    def test_rollback_on_error(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)

        with pytest.raises(RuntimeError, match="oops"):
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO t1 VALUES (%s)", (1,))
                raise RuntimeError("oops")

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    def test_cursor_is_yielded(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db = _create_db_with_mock_pool(mock_conn)

        with db.transaction() as cursor:
            assert cursor is mock_cursor


# ─── close 测试 ──────────────────────────────────────────────────


class TestClose:
    """测试 close 方法。"""

    def test_close_calls_pool_close_all(self) -> None:
        with patch("scdb_mysql_speed.core.ConnectionPool"):
            db = SCDBMySQLSpeed(_make_meta())
        db._pool = MagicMock()
        db.close()
        db._pool.close_all.assert_called_once()


# ─── repr 测试 ───────────────────────────────────────────────────


class TestRepr:
    """测试 __repr__ 方法。"""

    def test_repr_format(self) -> None:
        with patch("scdb_mysql_speed.core.ConnectionPool"):
            db = SCDBMySQLSpeed(_make_meta())
        assert "localhost" in repr(db)
        assert "test" in repr(db)
