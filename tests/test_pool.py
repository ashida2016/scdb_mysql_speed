"""ConnectionPool 连接池的单元测试（使用 mock）。"""

from unittest.mock import MagicMock, patch, PropertyMock
import queue

import pytest

from scdb_mysql_speed.meta import SCDBMySQLMeta
from scdb_mysql_speed.pool import ConnectionPool, _PooledConnection
from scdb_mysql_speed.exceptions import SCDBConnectionError, SCDBPoolError


def _make_meta(**overrides) -> SCDBMySQLMeta:
    """创建测试用 SCDBMySQLMeta。"""
    defaults = dict(
        host="localhost",
        user="root",
        password="",
        database="test",
        pool_size=2,
        pool_max_overflow=3,
        pool_timeout=5,
        pool_recycle=3600,
    )
    defaults.update(overrides)
    return SCDBMySQLMeta(**defaults)


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestConnectionPoolInit:
    """测试连接池初始化。"""

    def test_prefills_pool_size_connections(self, mock_mysqldb) -> None:
        mock_conn = MagicMock()
        mock_mysqldb.connect.return_value = mock_conn

        meta = _make_meta(pool_size=3)
        pool = ConnectionPool(meta)

        assert mock_mysqldb.connect.call_count == 3
        assert pool.idle_count == 3
        pool.close_all()

    def test_prefill_failure_does_not_raise(self, mock_mysqldb) -> None:
        mock_mysqldb.connect.side_effect = Exception("connection refused")

        meta = _make_meta(pool_size=2)
        # 不应抛出异常
        pool = ConnectionPool(meta)
        assert pool.idle_count == 0
        pool.close_all()


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestGetConnection:
    """测试 get_connection 上下文管理器。"""

    def test_returns_connection(self, mock_mysqldb) -> None:
        mock_conn = MagicMock()
        mock_conn.ping.return_value = None
        mock_mysqldb.connect.return_value = mock_conn

        pool = ConnectionPool(_make_meta(pool_size=1))
        with pool.get_connection() as conn:
            assert conn is mock_conn
        pool.close_all()

    def test_connection_returned_to_pool(self, mock_mysqldb) -> None:
        mock_conn = MagicMock()
        mock_conn.ping.return_value = None
        mock_mysqldb.connect.return_value = mock_conn

        pool = ConnectionPool(_make_meta(pool_size=1))
        initial_idle = pool.idle_count

        with pool.get_connection():
            # 正在使用中，空闲数应该减少
            pass

        # 归还后空闲数应恢复
        assert pool.idle_count >= initial_idle
        pool.close_all()

    def test_raises_when_closed(self, mock_mysqldb) -> None:
        mock_mysqldb.connect.return_value = MagicMock()

        pool = ConnectionPool(_make_meta(pool_size=1))
        pool.close_all()

        with pytest.raises(SCDBPoolError, match="已关闭"):
            with pool.get_connection():
                pass

    def test_timeout_raises_pool_error(self, mock_mysqldb) -> None:
        """所有连接被占满且超时后应抛出 SCDBPoolError。"""
        mock_conn = MagicMock()
        mock_conn.ping.return_value = None
        mock_mysqldb.connect.return_value = mock_conn

        meta = _make_meta(pool_size=1, pool_max_overflow=0, pool_timeout=1)
        pool = ConnectionPool(meta)

        with pool.get_connection():
            # 池内唯一连接被占用，再次获取应超时
            with pytest.raises(SCDBPoolError, match="超时"):
                with pool.get_connection():
                    pass

        pool.close_all()


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestConnectionHealthCheck:
    """测试连接健康检查。"""

    def test_unhealthy_connection_is_discarded(self, mock_mysqldb) -> None:
        import MySQLdb as real_mysqldb_module

        # 设置 mock 的 Error 为真实的 MySQLdb.Error
        mock_mysqldb.Error = real_mysqldb_module.Error

        healthy_conn = MagicMock()
        healthy_conn.ping.return_value = None

        unhealthy_conn = MagicMock()
        # 必须抛出 MySQLdb.Error，因为 _is_alive 只捕获 MySQLdb.Error
        unhealthy_conn.ping.side_effect = real_mysqldb_module.Error("gone away")

        # 第一次创建（预填充）返回 unhealthy，第二次（新建）返回 healthy
        mock_mysqldb.connect.side_effect = [unhealthy_conn, healthy_conn]

        pool = ConnectionPool(_make_meta(pool_size=1))

        with pool.get_connection() as conn:
            assert conn is healthy_conn

        pool.close_all()


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestConnectionRecycling:
    """测试连接过期回收。"""

    @patch("scdb_mysql_speed.pool.time")
    def test_expired_connection_is_recycled(self, mock_time, mock_mysqldb) -> None:
        import MySQLdb as real_mysqldb_module
        mock_mysqldb.Error = real_mysqldb_module.Error

        old_conn = MagicMock()
        old_conn.ping.return_value = None
        new_conn = MagicMock()
        new_conn.ping.return_value = None

        mock_mysqldb.connect.side_effect = [old_conn, new_conn]

        # 时间调用顺序：
        # 1. _PooledConnection.__init__ (prefill) -> 0.0
        # 2. _is_expired check during get_connection -> 7200.0 (expired)
        # 3. _PooledConnection.__init__ (new connection) -> 7200.0
        # 4. _PooledConnection.__init__ (release/return to pool) -> 7200.0
        mock_time.monotonic.side_effect = [0.0, 7200.0, 7200.0, 7200.0]

        pool = ConnectionPool(_make_meta(pool_size=1, pool_recycle=3600))

        with pool.get_connection() as conn:
            # 旧连接过期，应使用新创建的连接
            assert conn is new_conn

        # 旧连接应已被关闭
        old_conn.close.assert_called()
        pool.close_all()


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestCloseAll:
    """测试关闭连接池。"""

    def test_closes_all_idle_connections(self, mock_mysqldb) -> None:
        conn1 = MagicMock()
        conn2 = MagicMock()
        mock_mysqldb.connect.side_effect = [conn1, conn2]

        pool = ConnectionPool(_make_meta(pool_size=2))
        pool.close_all()

        conn1.close.assert_called_once()
        conn2.close.assert_called_once()
        assert pool.idle_count == 0

    def test_close_all_is_idempotent(self, mock_mysqldb) -> None:
        mock_mysqldb.connect.return_value = MagicMock()

        pool = ConnectionPool(_make_meta(pool_size=1))
        pool.close_all()
        pool.close_all()  # 不应抛出异常


@patch("scdb_mysql_speed.pool.MySQLdb")
class TestExceptionOnConnect:
    """测试连接创建失败。"""

    def test_connect_error_raises_scdb_connection_error(self, mock_mysqldb) -> None:
        import MySQLdb as _mod

        mock_mysqldb.Error = _mod.Error if hasattr(_mod, 'Error') else Exception
        mock_mysqldb.connect.side_effect = mock_mysqldb.Error("access denied")

        meta = _make_meta(pool_size=0)  # 不预填充
        pool = ConnectionPool(meta)

        with pytest.raises(SCDBConnectionError, match="连接失败"):
            with pool.get_connection():
                pass

        pool.close_all()
