"""
Checkpointer Module: 实现 LangGraph 状态持久化。

MVP 阶段使用 SQLite 以降低运维复杂度。
生产阶段预留 PostgreSQL (pgvector) 切换路径。

职责对照: docs/implementation-plan-v1.md §3 & §5
"""

import os
import logging
import sqlite3
from contextlib import contextmanager
from typing import Optional, Union

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from app.config.settings import settings

logger = logging.getLogger("loom.checkpointer")


class CheckpointerFactory:
    """
    Checkpointer 工厂类：负责初始化并提供持久化适配器。
    支持 SQLite (MVP) 和 PostgreSQL (生产) 两种后端。
    """

    _sqlite_instance: Optional[AsyncSqliteSaver] = None

    @classmethod
    async def get_saver(cls) -> Union[AsyncSqliteSaver, "PostgresSaver"]:  # type: ignore[name-defined]
        """
        根据 DATABASE_URL 自动选择后端。
        """
        if settings.DATABASE_URL.startswith("postgresql"):
            return cls._get_postgres_saver()
        return await cls.get_sqlite_saver()

    @classmethod
    async def get_sqlite_saver(cls) -> AsyncSqliteSaver:
        """
        创建并返回 AsyncSqliteSaver (单例)。
        """
        if cls._sqlite_instance is not None:
            return cls._sqlite_instance

        db_path = settings.DATABASE_URL.replace("sqlite:///", "")

        # 确保父目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info("Created database directory: %s", db_dir)

        try:
            import aiosqlite
            conn = await aiosqlite.connect(db_path, check_same_thread=False)
            # 强制开启 WAL 模式以支持并发读取 (Streamlit 轮询)
            await conn.execute("PRAGMA journal_mode=WAL;")
            # 健康检查 (aiosqlite 连接成功即认为健康)

            # 注册允许序列化的模块。尝试包含所有可能的应用层路径。
            saver = AsyncSqliteSaver(conn, serde=JsonPlusSerializer(
                allowed_msgpack_modules=[
                    "app",
                    "app.core",
                    "app.core.state",
                    "app.core.supervisor",
                    "core.state",
                    "core.supervisor",
                    "enum",
                    "builtins",
                    "pydantic",
                    "langgraph.checkpoint.state"
                ]
            ))
            cls._sqlite_instance = saver
            logger.info("AsyncSqliteSaver initialized at %s", db_path)
            return saver

        except sqlite3.OperationalError as e:
            logger.error("SQLite operational error at %s: %s", db_path, e)
            raise RuntimeError(
                f"Failed to initialize SQLite database at {db_path}: {e}"
            ) from e
        except Exception as e:
            logger.error("Unexpected checkpointer initialization error: %s", e, exc_info=True)
            raise

    @classmethod
    def _get_postgres_saver(cls):
        """
        创建 PostgreSQL Checkpointer (生产预留)。
        需要安装: pip install langgraph-checkpoint-postgres
        """
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as e:
            raise ImportError(
                "PostgreSQL checkpointer requires 'langgraph-checkpoint-postgres'. "
                "Install with: pip install langgraph-checkpoint-postgres"
            ) from e

        try:
            saver = PostgresSaver.from_conn_string(settings.DATABASE_URL)
            # PostgresSaver 需要 setup() 初始化表结构
            saver.setup()
            logger.info("PostgresCheckpointer initialized")
            return saver
        except Exception as e:
            logger.error("Failed to initialize PostgresCheckpointer: %s", e, exc_info=True)
            raise RuntimeError(f"PostgreSQL checkpointer initialization failed: {e}") from e

    @classmethod
    def health_check(cls) -> bool:
        """
        连接健康探针。
        用于外部监控和 FastAPI healthcheck 端点。
        """
        try:
            if settings.DATABASE_URL.startswith("sqlite"):
                db_path = settings.DATABASE_URL.replace("sqlite:///", "")
                with sqlite3.connect(db_path) as conn:
                    conn.execute("SELECT 1;")
            else:
                cls._get_postgres_saver()
            return True
        except Exception as e:
            logger.error("Checkpointer health check failed: %s", e)
            cls._sqlite_instance = None
            return False

    @classmethod
    def reset(cls) -> None:
        """重置单例实例 (用于测试)"""
        if cls._sqlite_instance is not None:
            try:
                cls._sqlite_instance.conn.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            cls._sqlite_instance = None


@contextmanager
def get_db_connection():
    """提供原始数据库连接的上下文管理器 (供非图逻辑使用)"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    except sqlite3.Error as e:
        logger.error("Database connection error: %s", e)
        raise
    finally:
        if conn is not None:
            conn.close()
