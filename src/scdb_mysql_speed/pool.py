"""ConnectionPool — 线程安全的 MySQL 连接池。

基于 ``queue.Queue``（FIFO，线程安全）存储空闲连接，
使用 ``threading.Semaphore`` 控制最大并发连接总数。

特性：
- 连接健康检查（``ping()``）
- 连接过期回收（``pool_recycle``）
- 上下文管理器自动归还连接
- 延迟创建（首次获取时才建立连接）
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

import MySQLdb

from .exceptions import SCDBConnectionError, SCDBPoolError

if TYPE_CHECKING:
    from MySQLdb.connections import Connection

    from .meta import SCDBMySQLMeta

logger = logging.getLogger(__name__)


class _PooledConnection:
    """池化连接的薄包装，记录创建时间戳。"""

    __slots__ = ("connection", "created_at")

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.created_at: float = time.monotonic()


class ConnectionPool:
    """线程安全的 MySQL 连接池。

    Args:
        meta: 数据库连接配置。

    示例::

        pool = ConnectionPool(meta)
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
        pool.close_all()
    """

    def __init__(self, meta: SCDBMySQLMeta) -> None:
        self._meta = meta
        self._connect_kwargs: dict = meta.to_connect_kwargs()
        self._pool_recycle: int = meta.pool_recycle
        self._pool_timeout: int = meta.pool_timeout

        # 最大并发连接数 = pool_size + pool_max_overflow
        max_connections = meta.pool_size + meta.pool_max_overflow
        self._semaphore = threading.Semaphore(max_connections)

        # 空闲连接队列（无上限，由信号量控制总数）
        self._idle: queue.Queue[_PooledConnection] = queue.Queue()

        # 预填充核心连接
        for _ in range(meta.pool_size):
            try:
                pc = self._create_connection()
                self._idle.put_nowait(pc)
            except Exception:
                # 预填充失败不阻塞初始化，延迟到使用时再创建
                logger.warning("预填充连接失败，将延迟创建", exc_info=True)

        self._closed = False
        self._lock = threading.Lock()

    # ─── 公开 API ────────────────────────────────────────────────

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """获取一个数据库连接（上下文管理器，自动归还）。

        Yields:
            MySQLdb 连接对象。

        Raises:
            SCDBPoolError: 池已关闭或获取连接超时。
        """
        if self._closed:
            raise SCDBPoolError("连接池已关闭")

        # 获取信号量许可（限制总连接数）
        acquired = self._semaphore.acquire(timeout=self._pool_timeout)
        if not acquired:
            raise SCDBPoolError(
                f"从连接池获取连接超时（{self._pool_timeout}s），"
                f"已达到最大连接数上限"
            )

        conn: Connection | None = None
        try:
            conn = self._acquire()
            yield conn
        except Exception:
            # 连接可能已处于不确定状态，安全关闭后不归还
            if conn is not None:
                self._discard(conn)
                conn = None
            raise
        finally:
            if conn is not None:
                self._release(conn)
            self._semaphore.release()

    def close_all(self) -> None:
        """关闭连接池中的所有连接。

        调用后，池不可再使用。
        """
        with self._lock:
            self._closed = True

        while True:
            try:
                pc = self._idle.get_nowait()
                self._safe_close(pc.connection)
            except queue.Empty:
                break

        logger.info("连接池已关闭")

    @property
    def idle_count(self) -> int:
        """当前池中空闲连接数。"""
        return self._idle.qsize()

    # ─── 内部方法 ────────────────────────────────────────────────

    def _create_connection(self) -> _PooledConnection:
        """创建新的数据库连接。"""
        try:
            conn = MySQLdb.connect(**self._connect_kwargs)
            return _PooledConnection(conn)
        except MySQLdb.Error as e:
            raise SCDBConnectionError(f"创建数据库连接失败: {e}") from e

    def _acquire(self) -> Connection:
        """从空闲队列获取一个健康连接，或创建新连接。"""
        while True:
            try:
                pc = self._idle.get_nowait()
            except queue.Empty:
                # 没有空闲连接，创建新的
                pc = self._create_connection()
                return pc.connection

            # 检查连接是否过期
            if self._is_expired(pc):
                self._safe_close(pc.connection)
                continue

            # 健康检查
            if self._is_alive(pc.connection):
                return pc.connection

            # 不健康，关闭并继续尝试
            self._safe_close(pc.connection)

    def _release(self, conn: Connection) -> None:
        """将连接归还到空闲队列。"""
        if self._closed:
            self._safe_close(conn)
            return
        self._idle.put_nowait(_PooledConnection(conn))

    def _discard(self, conn: Connection) -> None:
        """丢弃一个连接（不归还池中）。"""
        self._safe_close(conn)

    def _is_expired(self, pc: _PooledConnection) -> bool:
        """检查连接是否已超过最大存活时间。"""
        return (time.monotonic() - pc.created_at) > self._pool_recycle

    @staticmethod
    def _is_alive(conn: Connection) -> bool:
        """通过 ping() 检测连接是否存活。"""
        try:
            conn.ping()
            return True
        except MySQLdb.Error:
            return False

    @staticmethod
    def _safe_close(conn: Connection) -> None:
        """安全关闭连接，忽略异常。"""
        try:
            conn.close()
        except Exception:
            pass
