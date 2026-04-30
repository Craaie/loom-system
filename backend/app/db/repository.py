"""
Chapter Repository: 负责小说章节的持久化存储与查询。
采用 Repository Pattern，支持未来从 SQLite 迁移至 PostgreSQL。
"""

import logging
import shutil
import os
from typing import List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Index, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from app.config.settings import settings

logger = logging.getLogger("loom.db")

Base = declarative_base()

class ProjectModel(Base):
    """顶级项目，用于聚合系列小说"""
    __tablename__ = "projects"
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    novels = relationship("NovelModel", back_populates="project", cascade="all, delete-orphan")

class NovelModel(Base):
    """项目下的小说作品"""
    __tablename__ = "novels"
    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"))
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    file_path = Column(String(512)) # 存储原小说文本路径
    meta_data = Column(Text) # JSON string
    latest_thread_id = Column(String(64)) # 最近一次任务 ID
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("ProjectModel", back_populates="novels")
    volumes = relationship("VolumeModel", back_populates="novel", cascade="all, delete-orphan")

class VolumeModel(Base):
    """小说下的卷次（如：第一部、第二部）"""
    __tablename__ = "volumes"
    id = Column(String(64), primary_key=True)
    novel_id = Column(String(64), ForeignKey("novels.id"))
    title = Column(String(255))
    index = Column(Integer, default=0)
    file_path = Column(String(512)) # 存储原卷次文本路径
    latest_thread_id = Column(String(64)) # 最近一次任务 ID
    created_at = Column(DateTime, default=datetime.utcnow)
    
    novel = relationship("NovelModel", back_populates="volumes")
    chapters = relationship("ChapterModel", back_populates="volume", cascade="all, delete-orphan")

class ChapterModel(Base):
    """章节数据库模型"""
    __tablename__ = "novel_chapters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    volume_id = Column(String(64), ForeignKey("volumes.id"), nullable=True) # 新增外键，暂许为空以兼容旧数据
    session_id = Column(String(64), nullable=False)
    index = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    processed_status = Column(Integer, default=0)  # 0:待处理, 1:分析中, 2:已完成
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    volume = relationship("VolumeModel", back_populates="chapters")
    
    # 索引优化查询
    __table_args__ = (
        Index("idx_session_chapter", "session_id", "index"),
        Index("idx_volume_chapter", "volume_id", "index"),
    )


class ThreadRunModel(Base):
    """任务运行态持久化记录。"""
    __tablename__ = "thread_runs"

    thread_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    current_node = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    is_finished = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class ChapterRepository:
    """项目/小说/章节 存储仓库"""
    
    def __init__(self, db_url: str = settings.DATABASE_URL):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self._migrate_db()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _migrate_db(self):
        """简单的数据库迁移逻辑，用于在开发阶段自动补全缺失列"""
        from sqlalchemy import inspect, text
        inspector = inspect(self.engine)
        
        # 检查 novels 表
        columns = [c["name"] for c in inspector.get_columns("novels")]
        if "file_path" not in columns:
            logger.info("📐 正在为 novels 表添加 file_path 列...")
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE novels ADD COLUMN file_path VARCHAR(512)"))
                conn.commit()

        # 检查 volumes 表
        columns = [c["name"] for c in inspector.get_columns("volumes")]
        if "file_path" not in columns:
            logger.info("📐 正在为 volumes 表添加 file_path 列...")
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE volumes ADD COLUMN file_path VARCHAR(512)"))
                conn.commit()

        # 检查 latest_thread_id (novels)
        columns = [c["name"] for c in inspector.get_columns("novels")]
        if "latest_thread_id" not in columns:
            logger.info("📐 正在为 novels 表添加 latest_thread_id 列...")
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE novels ADD COLUMN latest_thread_id VARCHAR(64)"))
                conn.commit()

        # 检查 latest_thread_id (volumes)
        columns = [c["name"] for c in inspector.get_columns("volumes")]
        if "latest_thread_id" not in columns:
            logger.info("📐 正在为 volumes 表添加 latest_thread_id 列...")
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE volumes ADD COLUMN latest_thread_id VARCHAR(64)"))
                conn.commit()

        # 检查 novel_chapters.summary
        columns = [c["name"] for c in inspector.get_columns("novel_chapters")]
        if "summary" not in columns:
            logger.info("📐 正在为 novel_chapters 表添加 summary 列...")
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE novel_chapters ADD COLUMN summary TEXT"))
                conn.commit()

    # --- Project 管理 ---
    def create_project(self, id: str, name: str, description: str = "") -> ProjectModel:
        db = self.SessionLocal()
        try:
            project = ProjectModel(id=id, name=name, description=description)
            db.add(project)
            db.commit()
            db.refresh(project)
            return project
        finally:
            db.close()

    def get_projects(self) -> List[ProjectModel]:
        db = self.SessionLocal()
        try:
            return db.query(ProjectModel).all()
        finally:
            db.close()

    def delete_project(self, project_id: str) -> bool:
        db = self.SessionLocal()
        try:
            project = db.query(ProjectModel).filter_by(id=project_id).first()
            if project:
                # 获取下属所有小说 ID 用于清理文件
                novel_ids = [n.id for n in project.novels]
                
                # 物理删除数据库记录 (带 cascade delete)
                db.delete(project)
                db.commit()
                
                # 清理所有关联小说的物理文件
                for nid in novel_ids:
                    upload_dir = os.path.join("uploads", nid)
                    if os.path.exists(upload_dir):
                        shutil.rmtree(upload_dir, ignore_errors=True)
                        logger.info(f"📁 已清理项目关联的小说目录: {upload_dir}")
                
                return True
            return False
        finally:
            db.close()

    # --- Novel 管理 ---
    def create_novel(self, id: str, project_id: str, title: str, author: str = "") -> NovelModel:
        db = self.SessionLocal()
        try:
            novel = NovelModel(id=id, project_id=project_id, title=title, author=author)
            db.add(novel)
            db.commit()
            db.refresh(novel)
            return novel
        finally:
            db.close()

    def get_novels(self, project_id: str) -> List[NovelModel]:
        db = self.SessionLocal()
        try:
            return db.query(NovelModel).filter_by(project_id=project_id).all()
        finally:
            db.close()

    def get_project_stats(self, project_id: str) -> dict:
        """获取项目的汇总统计数据"""
        db = self.SessionLocal()
        try:
            novels = db.query(NovelModel).filter_by(project_id=project_id).all()
            if not novels:
                return {"novel_count": 0, "chapter_count": 0, "total_words": 0, "project_id": project_id}
            
            novel_ids = [n.id for n in novels]
            
            from sqlalchemy import func
            total_words = db.query(func.sum(func.length(ChapterModel.content)))\
                .join(VolumeModel, ChapterModel.volume_id == VolumeModel.id)\
                .filter(VolumeModel.novel_id.in_(novel_ids)).scalar() or 0
                
            total_chapters = db.query(ChapterModel)\
                .join(VolumeModel, ChapterModel.volume_id == VolumeModel.id)\
                .filter(VolumeModel.novel_id.in_(novel_ids)).count()

            return {
                "novel_count": len(novels),
                "chapter_count": total_chapters,
                "total_words": total_words,
                "project_id": project_id
            }
        finally:
            db.close()

    def get_novel(self, id: str) -> Optional[NovelModel]:
        db = self.SessionLocal()
        try:
            return db.query(NovelModel).filter_by(id=id).first()
        finally:
            db.close()

    def get_volumes(self, novel_id: str) -> List[VolumeModel]:
        db = self.SessionLocal()
        try:
            return db.query(VolumeModel).filter_by(novel_id=novel_id).order_by(VolumeModel.index).all()
        finally:
            db.close()

    def delete_novel(self, id: str) -> bool:
        db = self.SessionLocal()
        try:
            novel = db.query(NovelModel).filter_by(id=id).first()
            if novel:
                # 物理删除数据库记录
                db.delete(novel)
                db.commit()
                
                # 物理删除上传的文件目录
                upload_dir = os.path.join("uploads", id)
                if os.path.exists(upload_dir):
                    shutil.rmtree(upload_dir, ignore_errors=True)
                    logger.info(f"📁 已清理小说上传目录: {upload_dir}")
                
                return True
            return False
        finally:
            db.close()

    # --- Volume 管理 ---
    def create_volume(self, id: str, novel_id: str, title: str, index: int = 0) -> VolumeModel:
        db = self.SessionLocal()
        try:
            volume = VolumeModel(id=id, novel_id=novel_id, title=title, index=index)
            db.add(volume)
            db.commit()
            db.refresh(volume)
            return volume
        finally:
            db.close()

    def delete_volume(self, id: str) -> bool:
        db = self.SessionLocal()
        try:
            volume = db.query(VolumeModel).filter_by(id=id).first()
            if volume:
                db.delete(volume)
                db.commit()
                return True
            return False
        finally:
            db.close()

    # --- Chapter 记录 ---
    def save_chapter(self, session_id: str, index: int, title: str, content: str, volume_id: str = None) -> None:
        """保存或更新单个章节"""
        db = self.SessionLocal()
        try:
            chapter = db.query(ChapterModel).filter_by(session_id=session_id, index=index).first()
            if chapter:
                chapter.title = title
                chapter.content = content
                if volume_id:
                    chapter.volume_id = volume_id
            else:
                chapter = ChapterModel(
                    session_id=session_id,
                    index=index,
                    title=title,
                    content=content,
                    volume_id=volume_id
                )
                db.add(chapter)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save chapter {index}: {e}")
            raise
        finally:
            db.close()

    def get_chapters(self, session_id: str = None, volume_id: str = None) -> List[ChapterModel]:
        """获取任务的所有章节，支持 session_id 或 volume_id 过滤"""
        db = self.SessionLocal()
        try:
            query = db.query(ChapterModel)
            if volume_id:
                query = query.filter_by(volume_id=volume_id)
            elif session_id:
                query = query.filter_by(session_id=session_id)
            return query.order_by(ChapterModel.index).all()
        finally:
            db.close()

    def get_chapters_by_volume(self, volume_id: str) -> List[ChapterModel]:
        return self.get_chapters(volume_id=volume_id)

    def get_chapter(self, session_id: str, index: int) -> Optional[ChapterModel]:
        """获取特定章节"""
        db = self.SessionLocal()
        try:
            return db.query(ChapterModel).filter_by(session_id=session_id, index=index).first()
        finally:
            db.close()

    def update_status(self, session_id: str, index: int, status: int) -> None:
        """更新处理状态"""
        db = self.SessionLocal()
        try:
            chapter = db.query(ChapterModel).filter_by(session_id=session_id, index=index).first()
            if chapter:
                chapter.processed_status = status
                db.commit()
        finally:
            db.close()

    def update_analysis_result(
        self,
        session_id: str,
        index: int,
        *,
        status: Optional[int] = None,
        summary: Optional[str] = None,
    ) -> None:
        """更新章节分析状态与摘要。"""
        db = self.SessionLocal()
        try:
            chapter = db.query(ChapterModel).filter_by(session_id=session_id, index=index).first()
            if chapter:
                if status is not None:
                    chapter.processed_status = status
                if summary is not None:
                    chapter.summary = summary
                db.commit()
        finally:
            db.close()

    def get_chapter_summaries(self, session_id: str) -> List[dict[str, Any]]:
        """按章节顺序返回已落库的摘要上下文。"""
        db = self.SessionLocal()
        try:
            rows = (
                db.query(ChapterModel)
                .filter(ChapterModel.session_id == session_id)
                .order_by(ChapterModel.index)
                .all()
            )
            return [
                {
                    "index": row.index,
                    "title": row.title or f"第{row.index + 1}章",
                    "summary": row.summary,
                }
                for row in rows
                if row.summary
            ]
        finally:
            db.close()

    def update_novel_file_path(self, novel_id: str, file_path: str):
        """更新小说的原文件路径"""
        db = self.SessionLocal()
        try:
            novel = db.query(NovelModel).filter(NovelModel.id == novel_id).first()
            if novel:
                novel.file_path = file_path
                db.commit()
        finally:
            db.close()

    def update_volume_file_path(self, volume_id: str, file_path: str):
        """更新卷次的原文件路径"""
        db = self.SessionLocal()
        try:
            volume = db.query(VolumeModel).filter(VolumeModel.id == volume_id).first()
            if volume:
                volume.file_path = file_path
                db.commit()
        finally:
            db.close()

    def update_novel_latest_thread(self, novel_id: str, thread_id: str):
        """更新小说关联的最新任务 ID"""
        db = self.SessionLocal()
        try:
            novel = db.query(NovelModel).filter(NovelModel.id == novel_id).first()
            if novel:
                novel.latest_thread_id = thread_id
                db.commit()
                logger.info(f"✅ 成功更新小说 {novel_id} 的 latest_thread_id 为 {thread_id}")
            else:
                logger.warning(f"⚠️ 未找到小说 {novel_id}，无法更新 latest_thread_id")
        finally:
            db.close()

    def update_volume_latest_thread(self, volume_id: str, thread_id: str):
        """更新卷次关联的最新任务 ID"""
        db = self.SessionLocal()
        try:
            volume = db.query(VolumeModel).filter(VolumeModel.id == volume_id).first()
            if volume:
                volume.latest_thread_id = thread_id
                db.commit()
                logger.info(f"✅ 成功更新卷次 {volume_id} 的 latest_thread_id 为 {thread_id}")
            else:
                logger.warning(f"⚠️ 未找到卷次 {volume_id}，无法更新 latest_thread_id")
        finally:
            db.close()

    def upsert_thread_run(
        self,
        thread_id: str,
        *,
        session_id: Optional[str] = None,
        status: str,
        current_node: Optional[str] = None,
        error: Optional[str] = None,
        finished: bool = False,
    ) -> None:
        """创建或更新任务运行记录。"""
        db = self.SessionLocal()
        try:
            record = db.query(ThreadRunModel).filter_by(thread_id=thread_id).first()
            now = datetime.utcnow()
            if record is None:
                record = ThreadRunModel(
                    thread_id=thread_id,
                    session_id=session_id,
                    status=status,
                    current_node=current_node,
                    error=error,
                    is_finished=finished,
                    finished_at=now if finished else None,
                )
                db.add(record)
            else:
                if session_id is not None:
                    record.session_id = session_id
                record.status = status
                record.current_node = current_node
                record.error = error
                record.is_finished = finished
                record.updated_at = now
                record.finished_at = now if finished else None
            db.commit()
        finally:
            db.close()

    def list_active_thread_ids(self) -> List[str]:
        """返回仍应视为活跃的线程 ID。"""
        db = self.SessionLocal()
        try:
            rows = (
                db.query(ThreadRunModel.thread_id)
                .filter(ThreadRunModel.is_finished.is_(False))
                .filter(ThreadRunModel.status.in_(["queued", "running", "waiting_approval"]))
                .all()
            )
            return [thread_id for (thread_id,) in rows]
        finally:
            db.close()

    def get_thread_run(self, thread_id: str) -> Optional[ThreadRunModel]:
        db = self.SessionLocal()
        try:
            return db.query(ThreadRunModel).filter_by(thread_id=thread_id).first()
        finally:
            db.close()


# --- 全局单例 ---
_repo_instance: Optional[ChapterRepository] = None


def get_repository() -> ChapterRepository:
    """获取全局 Repository 单例，避免每次请求都重建引擎和执行迁移检查"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = ChapterRepository()
    return _repo_instance

