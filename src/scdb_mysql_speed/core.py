"""SCDBMySQLSpeed — 高性能 MySQL 数据库操作主类。

提供完整的 CRUD 操作、多格式查询结果、分页、批量操作与事务支持。

示例::

    from scdb_mysql_speed import SCDBMySQLMeta, SCDBMySQLSpeed

    meta = SCDBMySQLMeta(host="127.0.0.1", user="root", password="pw", database="test")
    db = SCDBMySQLSpeed(meta)

    # 连接测试
    assert db.test_connection()

    # 查询
    rows = db.fetch_all("SELECT * FROM users", result_format="dict")
    page = db.fetch_page("SELECT * FROM users", page=2, page_size=10, result_format="df")

    # 增删改（自动事务）
    db.execute("INSERT INTO users (name) VALUES (%s)", ("Alice",))
    db.execute_many("INSERT INTO users (name) VALUES (%s)", [("Bob",), ("Charlie",)])

    # 手动事务
    with db.transaction() as cursor:
        cursor.execute("UPDATE users SET name=%s WHERE id=%s", ("Dave", 1))
        cursor.execute("DELETE FROM users WHERE id=%s", (2,))

    db.close()
"""

from __future__ import annotations

import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from typing import Any, Generator, Literal

import MySQLdb
from MySQLdb.cursors import Cursor, DictCursor

from .exceptions import (
    SCDBConnectionError,
    SCDBQueryError,
    SCDBTransactionError,
)
from .meta import SCDBMySQLMeta
from .pool import ConnectionPool

logger = logging.getLogger(__name__)

# 支持的返回格式类型
ResultFormat = Literal["tuple", "df", "json", "dict", "xml", "yaml", "csv"]


class SCDBMySQLSpeed:
    """高性能 MySQL 数据库操作类。

    通过连接池管理数据库连接，支持 CRUD 操作、多种结果格式、
    分页查询、批量操作和事务管理。

    Args:
        meta: 数据库连接配置元数据。
    """

    def __init__(self, meta: SCDBMySQLMeta) -> None:
        self._meta = meta
        self._pool = ConnectionPool(meta)
        logger.info(
            "SCDBMySQLSpeed 已初始化 (host=%s, db=%s, pool_size=%d)",
            meta.host,
            meta.database,
            meta.pool_size,
        )

    # ─── 连接管理 ────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """测试数据库连接是否可用。

        Returns:
            ``True`` 表示连接成功，``False`` 表示连接失败。
        """
        try:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result is not None and result[0] == 1
        except Exception as e:
            logger.error("连接测试失败: %s", e)
            return False

    def close(self) -> None:
        """关闭连接池，释放所有连接资源。

        调用后该实例不可再使用。
        """
        self._pool.close_all()
        logger.info("SCDBMySQLSpeed 已关闭")

    # ─── 查询（SELECT）───────────────────────────────────────────

    def fetch_all(
        self,
        sql: str,
        params: tuple | list | dict | None = None,
        result_format: ResultFormat = "tuple",
    ) -> Any:
        """执行查询并一次性返回所有结果。

        Args:
            sql: SQL 查询语句。
            params: 查询参数，用于参数化查询。
            result_format: 返回结果格式，支持
                ``"tuple"``（默认）、``"dict"``、``"df"``、``"json"``、
                ``"xml"``、``"yaml"``、``"csv"``。

        Returns:
            根据 *result_format* 返回对应格式的查询结果：

            - ``"tuple"``: ``tuple[tuple[Any, ...], ...]``
            - ``"dict"``: ``list[dict[str, Any]]``
            - ``"df"``: ``pandas.DataFrame``
            - ``"json"``: JSON 字符串
            - ``"xml"``: XML 字符串
            - ``"yaml"``: YAML 字符串
            - ``"csv"``: CSV 字符串

        Raises:
            SCDBQueryError: SQL 执行失败。
            ImportError: 使用 ``"df"`` 但未安装 ``pandas``，或使用
                ``"yaml"`` 但未安装 ``PyYAML``。
        """
        cursor_class = (
            DictCursor
            if result_format in ("dict", "json", "df", "xml", "yaml", "csv")
            else Cursor
        )

        try:
            with self._pool.get_connection() as conn:
                conn.autocommit(True)
                cursor = conn.cursor(cursor_class)
                try:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    columns = (
                        [desc[0] for desc in cursor.description]
                        if cursor.description
                        else []
                    )
                finally:
                    cursor.close()
        except MySQLdb.Error as e:
            raise SCDBQueryError(f"查询执行失败: {e}") from e

        return self._convert_result(rows, columns, result_format)

    def fetch_page(
        self,
        sql: str,
        params: tuple | list | dict | None = None,
        page: int = 1,
        page_size: int = 100,
        result_format: ResultFormat = "tuple",
    ) -> Any:
        """执行查询并返回指定页的结果（分页读取）。

        通过在 SQL 末尾自动追加 ``LIMIT offset, page_size`` 实现分页。
        传入的 SQL 不应包含 ``LIMIT`` 子句。

        Args:
            sql: SQL 查询语句（不含 LIMIT）。
            params: 查询参数。
            page: 页码，从 1 开始，默认 1。
            page_size: 每页行数，默认 100。
            result_format: 返回结果格式，同 :meth:`fetch_all`。

        Returns:
            指定页的查询结果，格式由 *result_format* 决定。

        Raises:
            ValueError: 页码或每页行数不合法。
            SCDBQueryError: SQL 执行失败。
        """
        if page < 1:
            raise ValueError(f"page 必须 >= 1，收到 {page}")
        if page_size < 1:
            raise ValueError(f"page_size 必须 >= 1，收到 {page_size}")

        offset = (page - 1) * page_size
        paged_sql = f"{sql.rstrip().rstrip(';')} LIMIT {offset}, {page_size}"

        return self.fetch_all(paged_sql, params, result_format)

    # ─── 增删改（带事务）─────────────────────────────────────────

    def execute(
        self,
        sql: str,
        params: tuple | list | dict | None = None,
    ) -> int:
        """执行单条增删改语句（自动事务：commit / rollback）。

        Args:
            sql: SQL 语句（INSERT / UPDATE / DELETE 等）。
            params: 语句参数。

        Returns:
            受影响的行数。

        Raises:
            SCDBQueryError: SQL 执行失败。
        """
        try:
            with self._pool.get_connection() as conn:
                conn.autocommit(False)
                cursor = conn.cursor()
                try:
                    cursor.execute(sql, params)
                    affected = cursor.rowcount
                    conn.commit()
                    return affected
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass  # 连接已断开，rollback 不可能成功
                    raise
                finally:
                    cursor.close()
        except MySQLdb.Error as e:
            raise SCDBQueryError(f"执行失败: {e}") from e

    def execute_many(
        self,
        sql: str,
        params_list: list[tuple | list | dict] | None = None,
    ) -> int:
        """批量执行增删改语句（使用 executemany，自动事务）。

        Args:
            sql: SQL 模板语句。
            params_list: 参数列表，每个元素对应一次执行的参数。

        Returns:
            受影响的总行数。

        Raises:
            SCDBQueryError: SQL 执行失败。
        """
        if not params_list:
            return 0

        try:
            with self._pool.get_connection() as conn:
                conn.autocommit(False)
                cursor = conn.cursor()
                try:
                    cursor.executemany(sql, params_list)
                    affected = cursor.rowcount
                    conn.commit()
                    return affected
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass  # 连接已断开，rollback 不可能成功
                    raise
                finally:
                    cursor.close()
        except MySQLdb.Error as e:
            raise SCDBQueryError(f"批量执行失败: {e}") from e

    # ─── 事务上下文管理器 ────────────────────────────────────────

    @contextmanager
    def transaction(self) -> Generator[Cursor, None, None]:
        """手动事务上下文管理器。

        在 ``with`` 块内可对同一个 cursor 执行多条 SQL，
        正常退出时自动 ``COMMIT``，异常时自动 ``ROLLBACK``。

        Yields:
            MySQLdb Cursor 对象。

        Raises:
            SCDBTransactionError: 事务提交或回滚失败。

        示例::

            with db.transaction() as cursor:
                cursor.execute("INSERT INTO t1 VALUES (%s)", (1,))
                cursor.execute("UPDATE t2 SET x=%s WHERE id=%s", (2, 3))
        """
        try:
            with self._pool.get_connection() as conn:
                conn.autocommit(False)
                cursor = conn.cursor()
                try:
                    yield cursor
                    conn.commit()
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        # 连接已断开，rollback 不可能成功，
                        # 让原始异常继续传播
                        pass
                    raise
                finally:
                    cursor.close()
        except MySQLdb.Error as e:
            raise SCDBTransactionError(f"事务操作失败: {e}") from e

    # ─── 内部工具方法 ────────────────────────────────────────────

    @staticmethod
    def _convert_result(
        rows: Any,
        columns: list[str],
        result_format: ResultFormat,
    ) -> Any:
        """将原始查询结果转换为指定格式。"""
        if result_format == "tuple":
            return rows

        if result_format == "dict":
            # DictCursor 已返回 list[dict]
            return list(rows) if not isinstance(rows, list) else rows

        if result_format == "json":
            dict_rows = list(rows) if not isinstance(rows, list) else rows
            return json.dumps(dict_rows, ensure_ascii=False, default=str)

        if result_format == "df":
            try:
                import pandas as pd
            except ImportError:
                raise ImportError(
                    "使用 result_format='df' 需要安装 pandas。"
                    "请执行: pip install scdb_mysql_speed[dataframe]"
                )
            # 使用 DictCursor 返回的 dict 列表直接构造
            dict_rows = list(rows) if not isinstance(rows, list) else rows
            return pd.DataFrame(dict_rows, columns=columns if columns else None)

        if result_format == "xml":
            dict_rows = list(rows) if not isinstance(rows, list) else rows
            root = ET.Element("results")
            for row in dict_rows:
                row_elem = ET.SubElement(root, "row")
                for key, value in row.items():
                    col_elem = ET.SubElement(row_elem, str(key))
                    col_elem.text = str(value) if value is not None else ""
            return ET.tostring(root, encoding="unicode", xml_declaration=True)

        if result_format == "yaml":
            try:
                import yaml
            except ImportError:
                raise ImportError(
                    "使用 result_format='yaml' 需要安装 PyYAML。"
                    "请执行: pip install scdb_mysql_speed[yaml]"
                )
            dict_rows = list(rows) if not isinstance(rows, list) else rows
            return yaml.dump(
                dict_rows, allow_unicode=True, default_flow_style=False,
            )

        if result_format == "csv":
            dict_rows = list(rows) if not isinstance(rows, list) else rows
            if not dict_rows:
                # 无数据时仅输出列头（若有）
                buf = io.StringIO()
                writer = csv.writer(buf)
                if columns:
                    writer.writerow(columns)
                return buf.getvalue()
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=columns or list(dict_rows[0].keys()))
            writer.writeheader()
            writer.writerows(dict_rows)
            return buf.getvalue()

        raise ValueError(f"不支持的 result_format: {result_format!r}")

    def __repr__(self) -> str:
        return (
            f"SCDBMySQLSpeed(host={self._meta.host!r}, "
            f"db={self._meta.database!r})"
        )

    def __del__(self) -> None:
        """析构时尝试关闭连接池。"""
        try:
            self._pool.close_all()
        except Exception:
            pass
