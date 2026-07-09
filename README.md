# scdb_mysql_speed

一个高性能、工业级的操作 MySQL 数据库的 Python 包。

## 特性

- 🚀 **高性能** — 基于 `mysqlclient`（C 扩展驱动），速度最快
- 🏊 **连接池化** — 自研线程安全连接池，支持健康检查与自动回收
- 📦 **多格式返回** — 查询结果支持 tuple / dict / DataFrame / JSON / XML / YAML / CSV
- 📄 **分页查询** — 内置分页读取与全量读取两种方式
- 🔄 **事务支持** — 增删改操作自动事务，也支持手动事务上下文
- ⚡ **批量操作** — 原生 `executemany` 批量插入/更新

## 安装

```bash
pip install -e .
```

如需 DataFrame 格式支持：

```bash
pip install -e ".[dataframe]"
```

如需 YAML 格式支持：

```bash
pip install -e ".[yaml]"
```

## 快速上手

```python
from scdb_mysql_speed import SCDBMySQLMeta, SCDBMySQLSpeed

# 1. 创建连接配置
meta = SCDBMySQLMeta(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="your_password",
    database="your_database",
)

# 2. 初始化数据库操作类
db = SCDBMySQLSpeed(meta)

# 3. 连接测试
assert db.test_connection()
```

## 帮助文档

[ver0.5.0](https://scdb-mysql-speed.readthedocs.io/zh-cn/ver0.5.0/)  
[ver0.4.0](https://scdb-mysql-speed.readthedocs.io/zh-cn/ver0.4.0/)  
[ver0.3.1](https://scdb-mysql-speed.readthedocs.io/zh-cn/ver0.3.1/)  

## 查询操作

### 全量查询

```python
# 默认 tuple 格式
rows = db.fetch_all("SELECT * FROM users")
# ((1, 'alice'), (2, 'bob'))

# dict 格式
rows = db.fetch_all("SELECT * FROM users", result_format="dict")
# [{'id': 1, 'name': 'alice'}, {'id': 2, 'name': 'bob'}]

# JSON 格式
data = db.fetch_all("SELECT * FROM users", result_format="json")
# '[{"id": 1, "name": "alice"}, ...]'

# DataFrame 格式（需安装 pandas）
df = db.fetch_all("SELECT * FROM users", result_format="df")
#    id   name
# 0   1  alice
# 1   2    bob

# XML 格式
xml_str = db.fetch_all("SELECT * FROM users", result_format="xml")
# '<?xml version="1.0" ?>\n<results><row><id>1</id><name>alice</name></row>...'

# YAML 格式（需安装 PyYAML）
yaml_str = db.fetch_all("SELECT * FROM users", result_format="yaml")
# - id: 1
#   name: alice
# - id: 2
#   name: bob

# CSV 格式
csv_str = db.fetch_all("SELECT * FROM users", result_format="csv")
# 'id,name\r\n1,alice\r\n2,bob\r\n'
```

### 分页查询

```python
# 第 1 页，每页 10 条
page1 = db.fetch_page("SELECT * FROM users", page=1, page_size=10)

# 第 3 页，dict 格式
page3 = db.fetch_page(
    "SELECT * FROM users",
    page=3, page_size=10,
    result_format="dict",
)
```

## 增删改操作

```python
# 单条插入（自动事务）
affected = db.execute(
    "INSERT INTO users (name, age) VALUES (%s, %s)",
    ("alice", 30),
)

# 批量插入（使用 executemany）
affected = db.execute_many(
    "INSERT INTO users (name, age) VALUES (%s, %s)",
    [("bob", 25), ("charlie", 35), ("dave", 28)],
)

# 更新
affected = db.execute(
    "UPDATE users SET age=%s WHERE name=%s",
    (31, "alice"),
)

# 删除
affected = db.execute(
    "DELETE FROM users WHERE id=%s",
    (1,),
)
```

## 事务管理

```python
# 手动事务 — 多条语句在同一事务中
with db.transaction() as cursor:
    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (%s, %s)", (1, 100))
    cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (100, 1))
# 正常退出自动 COMMIT，异常自动 ROLLBACK
```

## 连接配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | str | *(必填)* | 数据库主机地址 |
| `port` | int | 3306 | 数据库端口 |
| `user` | str | "root" | 用户名 |
| `password` | str | "" | 密码 |
| `database` | str | "" | 数据库名 |
| `charset` | str | "utf8mb4" | 字符集 |
| `connect_timeout` | int | 10 | 连接超时（秒） |
| `read_timeout` | int | 30 | 读取超时（秒） |
| `write_timeout` | int | 30 | 写入超时（秒） |
| `pool_size` | int | 5 | 连接池核心大小 |
| `pool_max_overflow` | int | 10 | 连接池最大溢出数 |
| `pool_timeout` | int | 30 | 获取连接超时（秒） |
| `pool_recycle` | int | 3600 | 连接最大存活时间（秒） |

## License

MIT
