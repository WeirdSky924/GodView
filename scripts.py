"""
项目启动脚本
"""

import os
import sys
import argparse
from pathlib import Path


def check_dependencies():
    """检查依赖是否已安装"""
    try:
        import fastapi
        import langchain
        import sqlalchemy
        print("[OK] 核心依赖已安装")
        return True
    except ImportError as e:
        print(f"[ERROR] 缺少依赖：{e}")
        print("请运行：pip install -r requirements.txt")
        return False


def start_server(host="0.0.0.0", port=8000, reload=False):
    """启动 FastAPI 服务器"""
    import uvicorn

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def init_database():
    """初始化数据库表结构"""
    import asyncio
    from app.database.postgres import PostgresDatabase
    from app.config import settings

    async def _init():
        db = PostgresDatabase(settings.database_url)
        await db.connect()
        await db.init_tables()
        await db.disconnect()
        print("[OK] 数据库初始化完成")

    asyncio.run(_init())


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="GodView 小说生成系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动服务器")
    start_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    start_parser.add_argument("--port", type=int, default=8000, help="监听端口")
    start_parser.add_argument("--reload", action="store_true", help="开发模式热重载")

    # init-db 命令
    subparsers.add_parser("init-db", help="初始化数据库")

    # check 命令
    subparsers.add_parser("check", help="检查环境依赖")

    args = parser.parse_args()

    if args.command == "start":
        if not check_dependencies():
            sys.exit(1)
        start_server(args.host, args.port, args.reload)
    elif args.command == "init-db":
        if not check_dependencies():
            sys.exit(1)
        init_database()
    elif args.command == "check":
        check_dependencies()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
