#!/usr/bin/env python3
"""
Godview 数据库备份脚本
用于迁移工作平台时备份所有数据

使用方法:
    python backup_database.py [--output-dir <目录>]

功能:
    1. 导出 PostgreSQL 数据库所有表
    2. 导出 Qdrant 向量数据库
    3. 打包为带时间戳的备份文件
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 数据库配置 - 从 docker-compose.yml 读取
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "password",
    "database": "godview",
}

QDRANT_CONFIG = {
    "host": "127.0.0.1",
    "port": 6333,
}

NEBULA_CONFIG = {
    "host": "127.0.0.1",
    "port": 9669,
    "user": "root",
    "password": "nebula",
    "space": "godview",
}


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_postgres(output_dir: Path) -> Path:
    """
    使用 pg_dump 导出 PostgreSQL 数据库

    Returns:
        Path: 备份文件路径
    """
    timestamp = get_timestamp()
    backup_file = output_dir / f"postgres_backup_{timestamp}.sql"

    print(f"[PostgreSQL] 开始备份数据库: {POSTGRES_CONFIG['database']}")

    # 设置 PGPASSWORD 环境变量
    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_CONFIG["password"]

    # 使用 pg_dump 导出
    cmd = [
        "pg_dump",
        "-h", POSTGRES_CONFIG["host"],
        "-p", str(POSTGRES_CONFIG["port"]),
        "-U", POSTGRES_CONFIG["user"],
        "-d", POSTGRES_CONFIG["database"],
        "-F", "p",  # plain SQL format
        "-f", str(backup_file),
        "--no-owner",  # 不导出所有者信息
        "--no-acl",    # 不导出访问权限
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[PostgreSQL] pg_dump 警告: {result.stderr}")
            # 检查文件是否创建成功
            if backup_file.exists() and backup_file.stat().st_size > 0:
                print(f"[PostgreSQL] 备份完成（部分成功）: {backup_file}")
            else:
                raise Exception(f"pg_dump 失败: {result.stderr}")
        else:
            print(f"[PostgreSQL] 备份完成: {backup_file}")
            print(f"[PostgreSQL] 文件大小: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")

        return backup_file
    except FileNotFoundError:
        print("[PostgreSQL] pg_dump 未安装，尝试使用 Python 导出...")
        return backup_postgres_python(output_dir)


def backup_postgres_python(output_dir: Path) -> Path:
    """
    使用 Python asyncpg 导出 PostgreSQL 数据库
    （当 pg_dump 不可用时的备选方案）
    """
    import asyncio

    timestamp = get_timestamp()
    backup_file = output_dir / f"postgres_backup_{timestamp}.json"

    print(f"[PostgreSQL] 使用 Python 导出数据库...")

    async def export_data():
        import asyncpg

        conn = await asyncpg.connect(
            host=POSTGRES_CONFIG["host"],
            port=POSTGRES_CONFIG["port"],
            user=POSTGRES_CONFIG["user"],
            password=POSTGRES_CONFIG["password"],
            database=POSTGRES_CONFIG["database"],
        )

        # 获取所有表名
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        backup_data = {
            "metadata": {
                "timestamp": timestamp,
                "database": POSTGRES_CONFIG["database"],
                "tables_count": len(tables),
            },
            "tables": {},
        }

        for table in tables:
            table_name = table["table_name"]
            print(f"[PostgreSQL] 导出表: {table_name}")

            # 获取表数据
            rows = await conn.fetch(f"SELECT * FROM {table_name}")

            # 获取列名
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = $1
                ORDER BY ordinal_position
            """, table_name)

            # 转换为可序列化格式
            table_data = []
            for row in rows:
                row_dict = {}
                for col in columns:
                    col_name = col["column_name"]
                    value = row[col_name]
                    # 处理特殊类型
                    if isinstance(value, (bytes, memoryview)):
                        value = value.hex()
                    elif hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    row_dict[col_name] = value
                table_data.append(row_dict)

            backup_data["tables"][table_name] = {
                "columns": [c["column_name"] for c in columns],
                "column_types": {c["column_name"]: c["data_type"] for c in columns},
                "rows": table_data,
                "row_count": len(table_data),
            }

        await conn.close()
        return backup_data

    backup_data = asyncio.run(export_data())

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"[PostgreSQL] 备份完成: {backup_file}")
    print(f"[PostgreSQL] 文件大小: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")

    return backup_file


def backup_qdrant(output_dir: Path) -> Path:
    """
    导出 Qdrant 向量数据库

    Returns:
        Path: 备份文件路径
    """
    timestamp = get_timestamp()
    backup_file = output_dir / f"qdrant_backup_{timestamp}.json"

    print(f"[Qdrant] 开始备份向量数据库...")

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import models

        client = QdrantClient(
            host=QDRANT_CONFIG["host"],
            port=QDRANT_CONFIG["port"],
        )

        # 获取所有集合
        collections = client.get_collections()
        print(f"[Qdrant] 发现 {len(collections.collections)} 个集合")

        backup_data = {
            "metadata": {
                "timestamp": timestamp,
                "collections_count": len(collections.collections),
            },
            "collections": {},
        }

        for collection_info in collections.collections:
            collection_name = collection_info.name
            print(f"[Qdrant] 导出集合: {collection_name}")

            try:
                # 获取集合详情
                collection_detail = client.get_collection(collection_name)

                # 导出所有点（分批获取）
                all_points = []
                offset = None
                batch_size = 1000

                while True:
                    result = client.scroll(
                        collection_name=collection_name,
                        limit=batch_size,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,
                    )

                    points, next_offset = result
                    if not points:
                        break

                    for point in points:
                        point_data = {
                            "id": str(point.id),
                            "payload": point.payload,
                            "vector": point.vector,
                        }
                        all_points.append(point_data)

                    if next_offset is None:
                        break
                    offset = next_offset

                backup_data["collections"][collection_name] = {
                    "points": all_points,
                    "points_count": len(all_points),
                    "vectors_count": collection_detail.points_count,
                }
                print(f"[Qdrant] 集合 {collection_name}: {len(all_points)} 个点")

            except Exception as e:
                print(f"[Qdrant] 集合 {collection_name} 导出失败: {e}")
                backup_data["collections"][collection_name] = {
                    "error": str(e),
                    "points": [],
                    "points_count": 0,
                }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        print(f"[Qdrant] 备份完成: {backup_file}")
        print(f"[Qdrant] 文件大小: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")

        return backup_file

    except ImportError:
        print("[Qdrant] qdrant-client 未安装，跳过向量数据库备份")
        return None
    except Exception as e:
        print(f"[Qdrant] 备份失败: {e}")
        return None


def backup_nebula(output_dir: Path) -> Path:
    """
    导出 NebulaGraph 图数据库

    Returns:
        Path: 备份文件路径
    """
    timestamp = get_timestamp()
    backup_file = output_dir / f"nebula_backup_{timestamp}.json"

    print(f"[NebulaGraph] 开始备份图数据库...")

    try:
        from nebula3.gclient.net import ConnectionPool
        from nebula3.Config import Config

        # 创建连接池
        config = Config()
        config.max_connection_pool_size = 10
        config.timeout = 10000

        pool = ConnectionPool()
        init_result = pool.init([(NEBULA_CONFIG["host"], NEBULA_CONFIG["port"])], config)

        if not init_result:
            print(f"[NebulaGraph] 无法连接到 {NEBULA_CONFIG['host']}:{NEBULA_CONFIG['port']}")
            return None

        # 获取会话
        session = pool.get_session(NEBULA_CONFIG["user"], NEBULA_CONFIG["password"])

        backup_data = {
            "metadata": {
                "timestamp": timestamp,
                "host": NEBULA_CONFIG["host"],
                "port": NEBULA_CONFIG["port"],
                "space": NEBULA_CONFIG["space"],
            },
            "tags": {},  # 点类型
            "edges": {},  # 边类型
            "vertices": {},  # 点数据
            "relationships": {},  # 边数据
        }

        space_name = NEBULA_CONFIG["space"]

        # 使用图空间
        result = session.execute(f"USE {space_name}")
        if not result.is_succeeded():
            print(f"[NebulaGraph] 无法使用空间 {space_name}: {result.error_msg()}")
            session.release()
            pool.close()
            return None

        # 1. 获取所有 Tag（点类型）
        result = session.execute("SHOW TAGS")
        if result.is_succeeded():
            tags = []
            # 兼容不同版本的 API
            if hasattr(result, 'data') and result.data:
                rows = result.data.rows()
            elif hasattr(result, 'rows'):
                rows = result.rows()
            else:
                rows = []
            for row in rows:
                if hasattr(row, 'values'):
                    tag_name = row.values[0].get_s() if hasattr(row.values[0], 'get_s') else str(row.values[0])
                else:
                    tag_name = str(row[0]) if row else ""
                if tag_name:
                    tags.append(tag_name)
            backup_data["tags"] = tags
            print(f"[NebulaGraph] 发现 {len(tags)} 个 Tag: {tags}")

        # 2. 获取所有 Edge（边类型）
        result = session.execute("SHOW EDGES")
        if result.is_succeeded():
            edges = []
            if hasattr(result, 'data') and result.data:
                rows = result.data.rows()
            elif hasattr(result, 'rows'):
                rows = result.rows()
            else:
                rows = []
            for row in rows:
                if hasattr(row, 'values'):
                    edge_name = row.values[0].get_s() if hasattr(row.values[0], 'get_s') else str(row.values[0])
                else:
                    edge_name = str(row[0]) if row else ""
                if edge_name:
                    edges.append(edge_name)
            backup_data["edges"] = edges
            print(f"[NebulaGraph] 发现 {len(edges)} 个 Edge: {edges}")

        # 3. 导出所有点数据
        for tag in backup_data["tags"]:
            print(f"[NebulaGraph] 导出 Tag: {tag}")
            try:
                # 使用 FETCH 导出点数据（更兼容的 API）
                result = session.execute(f"FETCH PROP ON {tag} * YIELD vertex as v")
                vertices = []
                if result.is_succeeded():
                    if hasattr(result, 'data') and result.data:
                        rows = result.data.rows()
                    elif hasattr(result, 'rows'):
                        rows = result.rows()
                    else:
                        rows = []

                    for row in rows:
                        vertex_data = {}
                        try:
                            if hasattr(row, 'values'):
                                # 解析 vertex 对象
                                v = row.values[0]
                                if hasattr(v, 'as_node'):
                                    node = v.as_node()
                                    if hasattr(node, 'get_id'):
                                        vertex_data["id"] = str(node.get_id())
                                    if hasattr(node, 'properties'):
                                        props = node.properties()
                                        for key, val in props.items() if hasattr(props, 'items') else []:
                                            if hasattr(val, 'get_s'):
                                                vertex_data[key] = val.get_s()
                                            elif hasattr(val, 'get_i'):
                                                vertex_data[key] = val.get_i()
                                            else:
                                                vertex_data[key] = str(val)
                        except Exception as e:
                            continue

                        if vertex_data:
                            vertices.append(vertex_data)

                backup_data["vertices"][tag] = vertices
                print(f"[NebulaGraph] Tag {tag}: {len(vertices)} 个点")

            except Exception as e:
                print(f"[NebulaGraph] Tag {tag} 导出失败: {e}")
                backup_data["vertices"][tag] = []

        # 4. 导出所有边数据
        for edge in backup_data["edges"]:
            print(f"[NebulaGraph] 导出 Edge: {edge}")
            try:
                # 使用 FETCH 导出边数据
                result = session.execute(f"FETCH PROP ON {edge} * YIELD edge as e")
                relationships = []
                if result.is_succeeded():
                    if hasattr(result, 'data') and result.data:
                        rows = result.data.rows()
                    elif hasattr(result, 'rows'):
                        rows = result.rows()
                    else:
                        rows = []

                    for row in rows:
                        edge_data = {}
                        try:
                            if hasattr(row, 'values'):
                                e = row.values[0]
                                if hasattr(e, 'as_relationship'):
                                    rel = e.as_relationship()
                                    if hasattr(rel, 'start_vertex_id'):
                                        edge_data["src"] = str(rel.start_vertex_id())
                                    if hasattr(rel, 'end_vertex_id'):
                                        edge_data["dst"] = str(rel.end_vertex_id())
                                    if hasattr(rel, 'properties'):
                                        props = rel.properties()
                                        for key, val in props.items() if hasattr(props, 'items') else []:
                                            if hasattr(val, 'get_s'):
                                                edge_data[key] = val.get_s()
                                            elif hasattr(val, 'get_i'):
                                                edge_data[key] = val.get_i()
                                            else:
                                                edge_data[key] = str(val)
                        except Exception as e:
                            continue

                        if edge_data:
                            relationships.append(edge_data)

                backup_data["relationships"][edge] = relationships
                print(f"[NebulaGraph] Edge {edge}: {len(relationships)} 条边")

            except Exception as e:
                print(f"[NebulaGraph] Edge {edge} 导出失败: {e}")
                backup_data["relationships"][edge] = []

        session.release()
        pool.close()

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        print(f"[NebulaGraph] 备份完成: {backup_file}")
        print(f"[NebulaGraph] 文件大小: {backup_file.stat().st_size / 1024:.2f} KB")

        return backup_file

    except ImportError:
        print("[NebulaGraph] nebula3-python 未安装，跳过图数据库备份")
        return None
    except Exception as e:
        print(f"[NebulaGraph] 备份失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def backup_config(output_dir: Path) -> Path:
    """
    备份配置文件

    Returns:
        Path: 备份文件路径
    """
    timestamp = get_timestamp()
    backup_file = output_dir / f"config_backup_{timestamp}.json"

    print(f"[Config] 备份配置文件...")

    config_data = {
        "metadata": {
            "timestamp": timestamp,
        },
        "files": {},
    }

    # 要备份的配置文件列表
    config_files = [
        ".env",
        "docker-compose.yml",
    ]

    for filename in config_files:
        filepath = Path(__file__).parent / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                # 敏感信息脱敏
                if filename == ".env":
                    lines = []
                    for line in content.split("\n"):
                        if "API_KEY" in line or "PASSWORD" in line or "SECRET" in line:
                            # 脱敏处理
                            if "=" in line:
                                key, _ = line.split("=", 1)
                                lines.append(f"{key}=***REDACTED***")
                            else:
                                lines.append(line)
                        else:
                            lines.append(line)
                    content = "\n".join(lines)
                config_data["files"][filename] = content
            print(f"[Config] 已备份: {filename}")

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    print(f"[Config] 备份完成: {backup_file}")

    return backup_file


def create_restore_script(output_dir: Path):
    """
    创建恢复脚本
    """
    restore_script = output_dir / "restore_database.py"

    script_content = '''#!/usr/bin/env python3
"""
Godview 数据库恢复脚本
用于从备份恢复数据

使用方法:
    python restore_database.py <备份目录>
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "password",
    "database": "godview",
}

QDRANT_CONFIG = {
    "host": "127.0.0.1",
    "port": 6333,
}

NEBULA_CONFIG = {
    "host": "127.0.0.1",
    "port": 9669,
    "user": "root",
    "password": "nebula",
    "space": "godview",
}


def restore_postgres_sql(backup_file: Path):
    """从 SQL 文件恢复 PostgreSQL 数据库"""
    print(f"[PostgreSQL] 从 SQL 文件恢复: {backup_file}")

    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_CONFIG["password"]

    cmd = [
        "psql",
        "-h", POSTGRES_CONFIG["host"],
        "-p", str(POSTGRES_CONFIG["port"]),
        "-U", POSTGRES_CONFIG["user"],
        "-d", POSTGRES_CONFIG["database"],
        "-f", str(backup_file),
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[PostgreSQL] 恢复警告: {result.stderr}")
    else:
        print(f"[PostgreSQL] 恢复完成")


async def restore_postgres_json(backup_file: Path):
    """从 JSON 文件恢复 PostgreSQL 数据库"""
    print(f"[PostgreSQL] 从 JSON 文件恢复: {backup_file}")

    import asyncpg

    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    conn = await asyncpg.connect(
        host=POSTGRES_CONFIG["host"],
        port=POSTGRES_CONFIG["port"],
        user=POSTGRES_CONFIG["user"],
        password=POSTGRES_CONFIG["password"],
        database=POSTGRES_CONFIG["database"],
    )

    for table_name, table_data in backup_data.get("tables", {}).items():
        if not table_data.get("rows"):
            continue

        print(f"[PostgreSQL] 恢复表: {table_name} ({table_data['row_count']} 行)")

        columns = table_data["columns"]
        rows = table_data["rows"]

        # 构建插入语句
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        columns_str = ", ".join(columns)
        sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        for row in rows:
            values = [row.get(col) for col in columns]
            try:
                await conn.execute(sql, *values)
            except Exception as e:
                print(f"[PostgreSQL] 插入失败: {e}")

    await conn.close()
    print(f"[PostgreSQL] 恢复完成")


def restore_qdrant(backup_file: Path):
    """从 JSON 文件恢复 Qdrant 向量数据库"""
    print(f"[Qdrant] 从备份恢复: {backup_file}")

    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct

    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    client = QdrantClient(
        host=QDRANT_CONFIG["host"],
        port=QDRANT_CONFIG["port"],
    )

    for collection_name, collection_data in backup_data.get("collections", {}).items():
        points = collection_data.get("points", [])
        if not points:
            continue

        print(f"[Qdrant] 恢复集合: {collection_name} ({len(points)} 点)")

        # 创建集合（如果不存在）
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=len(points[0].get("vector", [])),
                    distance=Distance.COSINE,
                ),
            )
        except Exception:
            pass  # 集合已存在

        # 批量插入点
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            point_structs = [
                PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p.get("payload", {}),
                )
                for p in batch
            ]
            client.upsert(collection_name=collection_name, points=point_structs)

    print(f"[Qdrant] 恢复完成")


def restore_nebula(backup_file: Path):
    """从 JSON 文件恢复 NebulaGraph 图数据库"""
    print(f"[NebulaGraph] 从备份恢复: {backup_file}")

    from nebula3.gclient.net import ConnectionPool
    from nebula3.Config import Config

    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    # 创建连接池
    config = Config()
    config.max_connection_pool_size = 10
    config.timeout = 10000

    pool = ConnectionPool()
    pool.init([(NEBULA_CONFIG["host"], NEBULA_CONFIG["port"])], config)
    session = pool.get_session(NEBULA_CONFIG["user"], NEBULA_CONFIG["password"])

    space_name = backup_data["metadata"].get("space", NEBULA_CONFIG["space"])

    # 使用图空间
    session.execute(f"USE {space_name}")

    # 恢复点数据
    for tag, vertices in backup_data.get("vertices", {}).items():
        if not vertices:
            continue
        print(f"[NebulaGraph] 恢复 Tag: {tag} ({len(vertices)} 点)")
        for vertex in vertices:
            vid = vertex.get("id")
            if not vid:
                continue
            # 构建属性
            props = []
            for key, value in vertex.items():
                if key != "id":
                    if isinstance(value, str):
                        props.append(f'{key}: "{value}"')
                    elif isinstance(value, (int, float)):
                        props.append(f'{key}: {value}')
                    elif isinstance(value, bool):
                        props.append(f'{key}: {str(value).lower()}')
            if props:
                props_str = ", ".join(props)
                sql = f'INSERT VERTEX IF NOT EXISTS {tag} ({", ".join([k for k in vertex.keys() if k != "id"])}) VALUES "{vid}": ({props_str});'
                try:
                    session.execute(sql)
                except Exception as e:
                    print(f"[NebulaGraph] 插入点失败: {e}")

    # 恢复边数据
    for edge, relationships in backup_data.get("relationships", {}).items():
        if not relationships:
            continue
        print(f"[NebulaGraph] 恢复 Edge: {edge} ({len(relationships)} 边)")
        for rel in relationships:
            src = rel.get("src")
            dst = rel.get("dst")
            if not src or not dst:
                continue
            # 构建属性
            props = []
            prop_keys = []
            for key, value in rel.items():
                if key not in ["src", "dst"]:
                    prop_keys.append(key)
                    if isinstance(value, str):
                        props.append(f'"{value}"')
                    elif isinstance(value, (int, float)):
                        props.append(str(value))
                    elif isinstance(value, bool):
                        props.append(str(value).lower())
            if props:
                props_str = ", ".join(props)
                keys_str = ", ".join(prop_keys) if prop_keys else ""
                sql = f'INSERT EDGE IF NOT EXISTS {edge} ({keys_str}) VALUES "{src}"->"{dst}": ({props_str});'
                try:
                    session.execute(sql)
                except Exception as e:
                    print(f"[NebulaGraph] 插入边失败: {e}")

    session.release()
    pool.close()
    print(f"[NebulaGraph] 恢复完成")


def main():
    parser = argparse.ArgumentParser(description="恢复 Godview 数据库")
    parser.add_argument("backup_dir", type=str, help="备份目录路径")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    if not backup_dir.exists():
        print(f"错误: 备份目录不存在: {backup_dir}")
        sys.exit(1)

    # 查找备份文件
    sql_files = list(backup_dir.glob("postgres_backup_*.sql"))
    json_files = list(backup_dir.glob("postgres_backup_*.json"))
    qdrant_files = list(backup_dir.glob("qdrant_backup_*.json"))
    nebula_files = list(backup_dir.glob("nebula_backup_*.json"))

    # 恢复 PostgreSQL
    if sql_files:
        restore_postgres_sql(max(sql_files, key=lambda p: p.stat().st_mtime))
    elif json_files:
        asyncio.run(restore_postgres_json(max(json_files, key=lambda p: p.stat().st_mtime)))
    else:
        print("[PostgreSQL] 未找到备份文件")

    # 恢复 Qdrant
    if qdrant_files:
        restore_qdrant(max(qdrant_files, key=lambda p: p.stat().st_mtime))
    else:
        print("[Qdrant] 未找到备份文件")

    # 恢复 NebulaGraph
    if nebula_files:
        restore_nebula(max(nebula_files, key=lambda p: p.stat().st_mtime))
    else:
        print("[NebulaGraph] 未找到备份文件")

    print("\\n恢复完成!")


if __name__ == "__main__":
    main()
'''

    with open(restore_script, "w", encoding="utf-8") as f:
        f.write(script_content)

    print(f"[Restore] 恢复脚本已创建: {restore_script}")


def create_readme(output_dir: Path, backup_files: dict):
    """创建备份说明文件"""
    readme_file = output_dir / "README.md"

    content = f"""# Godview 数据库备份

## 备份时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 备份文件

| 文件 | 说明 |
|------|------|
| {backup_files.get('postgres', 'N/A')} | PostgreSQL 关系数据库备份 |
| {backup_files.get('qdrant', 'N/A')} | Qdrant 向量数据库备份 |
| {backup_files.get('nebula', 'N/A')} | NebulaGraph 图数据库备份 |
| {backup_files.get('config', 'N/A')} | 配置文件备份 |

## 恢复方法

### 方法 1: 使用恢复脚本
```bash
python restore_database.py ./backups/<备份目录>
```

### 方法 2: 手动恢复

#### PostgreSQL (SQL 格式)
```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d godview -f postgres_backup_*.sql
```

#### PostgreSQL (JSON 格式)
```bash
python restore_database.py ./backups/<备份目录>
```

#### Qdrant
```bash
python restore_database.py ./backups/<备份目录>
```

#### NebulaGraph
```bash
python restore_database.py ./backups/<备份目录>
```

## 注意事项

1. 恢复前请确保数据库服务已启动
2. 恢复会跳过已存在的数据 (ON CONFLICT DO NOTHING)
3. 配置文件中的敏感信息已脱敏，恢复后需要重新配置

## 数据库连接信息

- PostgreSQL: `postgresql://postgres:password@127.0.0.1:5432/godview`
- Qdrant: `http://127.0.0.1:6333`
- NebulaGraph: `127.0.0.1:9669` (space: godview)

## 数据库说明

### PostgreSQL (关系数据库)
存储项目、章节、角色、设定、技能等结构化数据。

### Qdrant (向量数据库)
存储文本嵌入向量，用于语义搜索和相似度匹配。

### NebulaGraph (图数据库)
存储角色关系、记忆关联、伏笔追踪等图结构数据。
"""

    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[README] 备份说明已创建: {readme_file}")


def main():
    parser = argparse.ArgumentParser(description="备份 Godview 数据库")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./backups",
        help="备份输出目录",
    )
    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    timestamp = get_timestamp()
    backup_dir = output_dir / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"=" * 60)
    print(f"Godview 数据库备份")
    print(f"备份目录: {backup_dir}")
    print(f"=" * 60)

    backup_files = {}

    # 1. 备份 PostgreSQL
    try:
        postgres_file = backup_postgres(backup_dir)
        backup_files["postgres"] = postgres_file.name
    except Exception as e:
        print(f"[PostgreSQL] 备份失败: {e}")

    # 2. 备份 Qdrant
    try:
        qdrant_file = backup_qdrant(backup_dir)
        if qdrant_file:
            backup_files["qdrant"] = qdrant_file.name
    except Exception as e:
        print(f"[Qdrant] 备份失败: {e}")

    # 3. 备份 NebulaGraph
    try:
        nebula_file = backup_nebula(backup_dir)
        if nebula_file:
            backup_files["nebula"] = nebula_file.name
    except Exception as e:
        print(f"[NebulaGraph] 备份失败: {e}")

    # 4. 备份配置文件
    try:
        config_file = backup_config(backup_dir)
        backup_files["config"] = config_file.name
    except Exception as e:
        print(f"[Config] 备份失败: {e}")

    # 5. 创建恢复脚本
    create_restore_script(backup_dir)

    # 6. 创建说明文件
    create_readme(backup_dir, backup_files)

    print(f"\\n" + "=" * 60)
    print(f"备份完成!")
    print(f"备份目录: {backup_dir}")
    print(f"=" * 60)

    # 计算总大小
    total_size = sum(f.stat().st_size for f in backup_dir.iterdir() if f.is_file())
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
