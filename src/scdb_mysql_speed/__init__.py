"""scdb_mysql_speed — 高性能、工业级的 MySQL 数据库操作 Python 包。

公开 API::

    from scdb_mysql_speed import SCDBMySQLMeta, SCDBMySQLSpeed

快速上手::

    meta = SCDBMySQLMeta(host="127.0.0.1", user="root", password="pw", database="mydb")
    db = SCDBMySQLSpeed(meta)
    db.test_connection()
    rows = db.fetch_all("SELECT * FROM users", result_format="dict")
    db.close()
"""

from .core import SCDBMySQLSpeed
from .exceptions import (
    SCDBConnectionError,
    SCDBError,
    SCDBPoolError,
    SCDBQueryError,
    SCDBTransactionError,
)
from .meta import SCDBMySQLMeta

__all__ = [
    "SCDBMySQLMeta",
    "SCDBMySQLSpeed",
    "SCDBError",
    "SCDBConnectionError",
    "SCDBPoolError",
    "SCDBQueryError",
    "SCDBTransactionError",
]

__version__ = "1.0.0"
