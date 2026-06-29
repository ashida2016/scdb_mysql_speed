"""SCDBMySQLSpeed 集成测试 — 基于真实 MySQL 数据库。

目标服务器: mysql.lan
测试数据库: test_5001
测试用户:   test5001 / Love2026
测试表:     t_test5001 (id INT AUTO_INCREMENT, name VARCHAR(255))

前置条件:
    在目标服务器上执行 tests/create_test_db.sql 初始化数据库：
    mysql -h mysql.lan -u root -p < tests/create_test_db.sql

运行方式:
    pytest tests/test_integration.py -v
"""

from time import sleep
import json

import pytest

from scdb_mysql_speed import SCDBMySQLMeta, SCDBMySQLSpeed
from scdb_mysql_speed.exceptions import SCDBQueryError

# ─── 固定配置 ────────────────────────────────────────────────────

TEST_META = SCDBMySQLMeta(
    host="mysql.lan",
    port=3306,
    user="test5001",
    password="Love2026",
    database="test_5001",
)


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db():
    """创建数据库连接实例（module 级别共享）。"""
    instance = SCDBMySQLSpeed(TEST_META)
    yield instance
    instance.close()


@pytest.fixture(autouse=True)
def clean_table(db):
    """每个测试前后清空测试表。"""
    # db.execute("TRUNCATE TABLE t_test5001")
    db.execute("DELETE FROM t_test5001")
    yield
    # db.execute("TRUNCATE TABLE t_test5001")
    db.execute("DELETE FROM t_test5001")


# ─── 连接测试 ────────────────────────────────────────────────────


class TestConnection:
    """连接测试。"""

    def test_connection_success(self, db) -> None:
        assert db.test_connection() is True

    def test_connection_failure(self) -> None:
        bad_meta = SCDBMySQLMeta(
            host="mysql.lan",
            user="nonexistent_user",
            password="wrong",
            database="test_5001",
            pool_size=1,
            pool_max_overflow=0,
            connect_timeout=3,
        )
        bad_db = SCDBMySQLSpeed(bad_meta)
        assert bad_db.test_connection() is False
        bad_db.close()


# ─── 插入操作 ────────────────────────────────────────────────────


class TestInsert:
    """INSERT 操作测试。"""

    def test_single_insert(self, db) -> None:
        affected = db.execute(
            "INSERT INTO t_test5001 (name) VALUES (%s)", ("Alice",)
        )
        assert affected == 1

    def test_insert_and_verify(self, db) -> None:
        db.execute("INSERT INTO t_test5001 (name) VALUES (%s)", ("Bob",))
        rows = db.fetch_all(
            "SELECT name FROM t_test5001 WHERE name = %s",
            ("Bob",),
            result_format="tuple",
        )
        assert len(rows) == 1
        assert rows[0][0] == "Bob"

    def test_batch_insert(self, db) -> None:
        data = [("Charlie",), ("Dave",), ("Eve",)]
        affected = db.execute_many(
            "INSERT INTO t_test5001 (name) VALUES (%s)", data
        )
        assert affected == 3

        rows = db.fetch_all("SELECT COUNT(*) FROM t_test5001")
        assert rows[0][0] == 3

    def test_batch_insert_empty(self, db) -> None:
        affected = db.execute_many(
            "INSERT INTO t_test5001 (name) VALUES (%s)", []
        )
        assert affected == 0


# ─── 查询操作 ────────────────────────────────────────────────────


class TestSelect:
    """SELECT 操作测试 — 多种返回格式。"""

    @pytest.fixture(autouse=True)
    def seed_data(self, db) -> None:
        """在每个测试前插入种子数据。"""
        db.execute_many(
            "INSERT INTO t_test5001 (name) VALUES (%s)",
            [("Alice",), ("Bob",), ("Charlie",)],
        )

    def test_fetch_all_tuple(self, db) -> None:
        rows = db.fetch_all(
            "SELECT id, name FROM t_test5001 ORDER BY id",
            result_format="tuple",
        )
        assert len(rows) == 3
        assert isinstance(rows, tuple)
        assert rows[0][1] == "Alice"

    def test_fetch_all_dict(self, db) -> None:
        rows = db.fetch_all(
            "SELECT id, name FROM t_test5001 ORDER BY id",
            result_format="dict",
        )
        assert len(rows) == 3
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)
        assert rows[0]["name"] == "Alice"
        assert "id" in rows[0]

    def test_fetch_all_json(self, db) -> None:
        result = db.fetch_all(
            "SELECT id, name FROM t_test5001 ORDER BY id",
            result_format="json",
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[1]["name"] == "Bob"

    def test_fetch_all_dataframe(self, db) -> None:
        pd = pytest.importorskip("pandas")
        df = db.fetch_all(
            "SELECT id, name FROM t_test5001 ORDER BY id",
            result_format="df",
        )
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["id", "name"]
        assert len(df) == 3
        assert df.iloc[2]["name"] == "Charlie"

    def test_fetch_all_with_params(self, db) -> None:
        rows = db.fetch_all(
            "SELECT name FROM t_test5001 WHERE name LIKE %s",
            ("%li%",),
            result_format="dict",
        )
        names = {r["name"] for r in rows}
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names

    def test_fetch_all_empty_result(self, db) -> None:
        rows = db.fetch_all(
            "SELECT * FROM t_test5001 WHERE name = %s",
            ("Nonexistent",),
        )
        assert len(rows) == 0


# ─── 分页查询 ────────────────────────────────────────────────────


class TestFetchPage:
    """分页查询测试。"""

    @pytest.fixture(autouse=True)
    def seed_data(self, db) -> None:
        """插入 10 条数据用于分页测试。"""
        data = [(f"User_{i:02d}",) for i in range(1, 11)]
        db.execute_many(
            "INSERT INTO t_test5001 (name) VALUES (%s)", data
        )

    def test_page_1(self, db) -> None:
        rows = db.fetch_page(
            "SELECT name FROM t_test5001 ORDER BY id",
            page=1, page_size=3,
        )
        assert len(rows) == 3

    def test_page_2(self, db) -> None:
        rows = db.fetch_page(
            "SELECT name FROM t_test5001 ORDER BY id",
            page=2, page_size=3,
            result_format="dict",
        )
        assert len(rows) == 3
        # 第 2 页应为 User_04, User_05, User_06
        assert rows[0]["name"] == "User_04"

    def test_page_last(self, db) -> None:
        """最后一页（不足 page_size 条）。"""
        rows = db.fetch_page(
            "SELECT name FROM t_test5001 ORDER BY id",
            page=4, page_size=3,
        )
        # 10 条数据，每页 3 条，第 4 页只有 1 条
        assert len(rows) == 1

    def test_page_beyond_last(self, db) -> None:
        """超出最后一页返回空结果。"""
        rows = db.fetch_page(
            "SELECT name FROM t_test5001 ORDER BY id",
            page=100, page_size=3,
        )
        assert len(rows) == 0

    def test_page_invalid_raises(self, db) -> None:
        with pytest.raises(ValueError):
            db.fetch_page("SELECT 1", page=0)

    def test_page_with_dataframe(self, db) -> None:
        pd = pytest.importorskip("pandas")
        df = db.fetch_page(
            "SELECT id, name FROM t_test5001 ORDER BY id",
            page=1, page_size=5,
            result_format="df",
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5


# ─── 更新操作 ────────────────────────────────────────────────────


class TestUpdate:
    """UPDATE 操作测试。"""

    def test_update_single_row(self, db) -> None:
        db.execute("INSERT INTO t_test5001 (name) VALUES (%s)", ("OldName",))
        affected = db.execute(
            "UPDATE t_test5001 SET name = %s WHERE name = %s",
            ("NewName", "OldName"),
        )
        assert affected == 1

        rows = db.fetch_all(
            "SELECT name FROM t_test5001 WHERE name = %s",
            ("NewName",),
        )
        assert len(rows) == 1

    def test_update_no_match(self, db) -> None:
        affected = db.execute(
            "UPDATE t_test5001 SET name = %s WHERE name = %s",
            ("X", "Nonexistent"),
        )
        assert affected == 0


# ─── 删除操作 ────────────────────────────────────────────────────


class TestDelete:
    """DELETE 操作测试。"""

    def test_delete_single_row(self, db) -> None:
        db.execute("INSERT INTO t_test5001 (name) VALUES (%s)", ("ToDelete",))
        affected = db.execute(
            "DELETE FROM t_test5001 WHERE name = %s", ("ToDelete",)
        )
        assert affected == 1

    def test_delete_multiple_rows(self, db) -> None:
        db.execute_many(
            "INSERT INTO t_test5001 (name) VALUES (%s)",
            [("Del1",), ("Del2",), ("Del3",)],
        )
        affected = db.execute("DELETE FROM t_test5001")
        assert affected == 3

    def test_delete_no_match(self, db) -> None:
        affected = db.execute(
            "DELETE FROM t_test5001 WHERE name = %s", ("Ghost",)
        )
        assert affected == 0


# ─── 事务测试 ────────────────────────────────────────────────────


class TestTransaction:
    """事务测试。"""

    def test_transaction_commit(self, db) -> None:
        """正常事务提交。"""
        with db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO t_test5001 (name) VALUES (%s)", ("TxnUser1",)
            )
            cursor.execute(
                "INSERT INTO t_test5001 (name) VALUES (%s)", ("TxnUser2",)
            )

        rows = db.fetch_all("SELECT COUNT(*) FROM t_test5001")
        assert rows[0][0] == 2

    def test_transaction_rollback(self, db) -> None:
        """异常时事务自动回滚。"""
        with pytest.raises(RuntimeError, match="故意失败"):
            with db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO t_test5001 (name) VALUES (%s)", ("RbUser",)
                )
                raise RuntimeError("故意失败")

        # 回滚后应无数据
        rows = db.fetch_all("SELECT COUNT(*) FROM t_test5001")
        assert rows[0][0] == 0

    def test_transaction_multi_operations(self, db) -> None:
        """事务中混合 INSERT + UPDATE。"""
        with db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO t_test5001 (name) VALUES (%s)", ("Original",)
            )
            cursor.execute(
                "UPDATE t_test5001 SET name = %s WHERE name = %s",
                ("Modified", "Original"),
            )

        rows = db.fetch_all(
            "SELECT name FROM t_test5001", result_format="dict"
        )
        assert len(rows) == 1
        assert rows[0]["name"] == "Modified"


# ─── 边界与异常测试 ──────────────────────────────────────────────


class TestEdgeCases:
    """边界与异常情况测试。"""

    def test_invalid_sql_raises(self, db) -> None:
        with pytest.raises(SCDBQueryError):
            db.fetch_all("SELECT * FROM nonexistent_table_xyz")

    def test_invalid_insert_raises(self, db) -> None:
        with pytest.raises(SCDBQueryError):
            db.execute("INSERT INTO nonexistent_table_xyz (x) VALUES (1)")

    def test_unicode_data(self, db) -> None:
        """UTF-8 中文数据读写。"""
        db.execute(
            "INSERT INTO t_test5001 (name) VALUES (%s)", ("测试用户",)
        )
        rows = db.fetch_all(
            "SELECT name FROM t_test5001 WHERE name = %s",
            ("测试用户",),
            result_format="dict",
        )
        assert rows[0]["name"] == "测试用户"

    def test_empty_string_data(self, db) -> None:
        db.execute("INSERT INTO t_test5001 (name) VALUES (%s)", ("",))
        rows = db.fetch_all("SELECT name FROM t_test5001", result_format="dict")
        assert rows[0]["name"] == ""

    def test_special_characters(self, db) -> None:
        """特殊字符（SQL 注入安全验证）。"""
        name = "O'Reilly; DROP TABLE--"
        db.execute(
            "INSERT INTO t_test5001 (name) VALUES (%s)", (name,)
        )
        rows = db.fetch_all(
            "SELECT name FROM t_test5001 WHERE name = %s",
            (name,),
            result_format="dict",
        )
        assert rows[0]["name"] == name

    def test_repr(self, db) -> None:
        r = repr(db)
        assert "mysql.lan" in r
        assert "test_5001" in r
