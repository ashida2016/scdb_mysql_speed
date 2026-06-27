"""scdb_mysql_speed 自定义异常层次结构。

所有异常均继承自 SCDBError，便于统一捕获：

    try:
        db.execute(...)
    except SCDBError as e:
        ...
"""


class SCDBError(Exception):
    """scdb_mysql_speed 基础异常。"""


class SCDBConnectionError(SCDBError):
    """数据库连接失败时抛出。"""


class SCDBPoolError(SCDBError):
    """连接池相关错误（获取超时、池已关闭等）。"""


class SCDBQueryError(SCDBError):
    """SQL 查询执行失败时抛出。"""


class SCDBTransactionError(SCDBError):
    """事务提交或回滚失败时抛出。"""
