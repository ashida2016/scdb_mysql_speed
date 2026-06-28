"""SCDBMySQLMeta — MySQL 连接配置数据类。

使用 frozen=True 保证不可变性，slots=True 减少内存开销。

Example:
    >>> meta = SCDBMySQLMeta(
    ...     host="127.0.0.1",
    ...     port=3306,
    ...     user="root",
    ...     password="secret",
    ...     database="mydb",
    ... )
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SCDBMySQLMeta:
    """MySQL 数据库连接元数据。

    Attributes:
        host: 数据库主机地址。
        port: 数据库端口，默认 3306。
        user: 用户名，默认 ``"root"``。
        password: 密码，默认空字符串。
        database: 数据库名称。
        charset: 字符集，默认 ``"utf8mb4"``。
        connect_timeout: 连接超时（秒），默认 10。
        read_timeout: 读取超时（秒），默认 30。
        write_timeout: 写入超时（秒），默认 30。
        pool_size: 连接池核心大小，默认 5。
        pool_max_overflow: 连接池最大溢出数，默认 10。
        pool_timeout: 从连接池获取连接的超时（秒），默认 30。
        pool_recycle: 连接最大存活时间（秒），默认 3600。
    """

    host: str
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30
    # 连接池配置
    pool_size: int = 5
    pool_max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600

    def to_connect_kwargs(self) -> dict:
        """转换为 ``MySQLdb.connect()`` 接受的关键字参数字典。

        Returns:
            包含 host, port, user, passwd, db, charset,
            connect_timeout, read_timeout, write_timeout 的字典。
        """
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "passwd": self.password,
            "db": self.database,
            "charset": self.charset,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "write_timeout": self.write_timeout,
        }
