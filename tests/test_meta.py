"""SCDBMySQLMeta 数据类的单元测试。"""

import pytest

from scdb_mysql_speed import SCDBMySQLMeta


class TestSCDBMySQLMetaDefaults:
    """测试默认值是否正确。"""

    def test_required_host(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.host == "localhost"

    def test_default_port(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.port == 3306

    def test_default_user(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.user == "root"

    def test_default_password(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.password == ""

    def test_default_database(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.database == ""

    def test_default_charset(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.charset == "utf8mb4"

    def test_default_timeouts(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.connect_timeout == 10
        assert meta.read_timeout == 30
        assert meta.write_timeout == 30

    def test_default_pool_settings(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        assert meta.pool_size == 5
        assert meta.pool_max_overflow == 10
        assert meta.pool_timeout == 30
        assert meta.pool_recycle == 3600


class TestSCDBMySQLMetaCustomValues:
    """测试自定义值。"""

    def test_all_custom_values(self) -> None:
        meta = SCDBMySQLMeta(
            host="db.example.com",
            port=3307,
            user="admin",
            password="s3cret",
            database="production",
            charset="utf8",
            connect_timeout=5,
            read_timeout=60,
            write_timeout=60,
            pool_size=10,
            pool_max_overflow=20,
            pool_timeout=15,
            pool_recycle=1800,
        )
        assert meta.host == "db.example.com"
        assert meta.port == 3307
        assert meta.user == "admin"
        assert meta.password == "s3cret"
        assert meta.database == "production"
        assert meta.charset == "utf8"
        assert meta.connect_timeout == 5
        assert meta.read_timeout == 60
        assert meta.write_timeout == 60
        assert meta.pool_size == 10
        assert meta.pool_max_overflow == 20
        assert meta.pool_timeout == 15
        assert meta.pool_recycle == 1800


class TestSCDBMySQLMetaFrozen:
    """测试不可变性（frozen=True）。"""

    def test_cannot_modify_host(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        with pytest.raises(AttributeError):
            meta.host = "other"  # type: ignore[misc]

    def test_cannot_modify_port(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        with pytest.raises(AttributeError):
            meta.port = 9999  # type: ignore[misc]

    def test_cannot_modify_pool_size(self) -> None:
        meta = SCDBMySQLMeta(host="localhost")
        with pytest.raises(AttributeError):
            meta.pool_size = 99  # type: ignore[misc]


class TestSCDBMySQLMetaToConnectKwargs:
    """测试 to_connect_kwargs() 方法。"""

    def test_returns_correct_keys(self) -> None:
        meta = SCDBMySQLMeta(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="pw",
            database="test_db",
        )
        kwargs = meta.to_connect_kwargs()
        assert kwargs == {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "passwd": "pw",
            "db": "test_db",
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        }

    def test_password_maps_to_passwd(self) -> None:
        """确认 password 字段映射为 MySQLdb 的 passwd 参数。"""
        meta = SCDBMySQLMeta(host="localhost", password="secret")
        kwargs = meta.to_connect_kwargs()
        assert "passwd" in kwargs
        assert kwargs["passwd"] == "secret"
        assert "password" not in kwargs

    def test_database_maps_to_db(self) -> None:
        """确认 database 字段映射为 MySQLdb 的 db 参数。"""
        meta = SCDBMySQLMeta(host="localhost", database="mydb")
        kwargs = meta.to_connect_kwargs()
        assert "db" in kwargs
        assert kwargs["db"] == "mydb"
        assert "database" not in kwargs

    def test_pool_settings_not_in_kwargs(self) -> None:
        """确认连接池配置不包含在连接参数中。"""
        meta = SCDBMySQLMeta(host="localhost")
        kwargs = meta.to_connect_kwargs()
        for key in ("pool_size", "pool_max_overflow", "pool_timeout", "pool_recycle"):
            assert key not in kwargs


class TestSCDBMySQLMetaSlots:
    """测试 slots 启用。"""

    def test_no_dict(self) -> None:
        """slots=True 的 dataclass 没有 __dict__。"""
        meta = SCDBMySQLMeta(host="localhost")
        assert not hasattr(meta, "__dict__")

    def test_cannot_add_attribute(self) -> None:
        """frozen + slots 阻止动态添加属性。"""
        meta = SCDBMySQLMeta(host="localhost")
        with pytest.raises((AttributeError, TypeError)):
            meta.extra = "nope"  # type: ignore[attr-defined]


class TestSCDBMySQLMetaEquality:
    """测试相等性比较。"""

    def test_equal_instances(self) -> None:
        m1 = SCDBMySQLMeta(host="localhost", database="db1")
        m2 = SCDBMySQLMeta(host="localhost", database="db1")
        assert m1 == m2

    def test_different_instances(self) -> None:
        m1 = SCDBMySQLMeta(host="localhost", database="db1")
        m2 = SCDBMySQLMeta(host="localhost", database="db2")
        assert m1 != m2
