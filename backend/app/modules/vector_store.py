"""
Vector Store Module: 负责向量库的统一访问与时序 RAG (Temporal RAG) 过滤。
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config.settings import settings

logger = logging.getLogger("loom.vector_store")

class VectorStoreManager:
    """向量库管理器，支持按 session_id 和 角色名隔离 Collection"""
    
    def __init__(self, session_id: str, provider: str = None):
        self.session_id = session_id
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.persist_directory = f"{settings.CHROMA_PERSIST_DIRECTORY}/{session_id}"
        
        # 初始化 Embedding
        if self.provider == "google":
            api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=api_key
            )
        else:
            api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
            self.embeddings = OpenAIEmbeddings(openai_api_key=api_key)

    def _get_safe_collection_name(self, character_name: str) -> str:
        """规范化 Collection 名称 (Chroma 仅支持 [a-zA-Z0-9._-])"""
        import hashlib
        # 移除非 ASCII 字符并加上哈希值以保证唯一性
        clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", character_name)
        if not clean_name or clean_name != character_name:
            # 包含非 ASCII 字符，通过哈希转换为 ASCII
            name_hash = hashlib.md5(character_name.encode("utf-8")).hexdigest()[:8]
            safe_name = f"char_{name_hash}"
        else:
            safe_name = f"char_{clean_name}"
            
        return safe_name[:63]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_store(self, character_name: str) -> Chroma:
        """获取特定角色的向量库"""
        collection_name = self._get_safe_collection_name(character_name)
        return Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )

    def add_character_trait(self, name: str, trait: Dict[str, Any], chapter_idx: int):
        """添加角色特征描述（带时序元数据）"""
        store = self.get_store(name)
        store.add_texts(
            texts=[json.dumps(trait, ensure_ascii=False)],
            metadatas=[{"chapter": chapter_idx, "character": name}]
        )

    def get_contextual_profile(self, name: str, current_chapter_idx: int) -> Dict[str, Any]:
        """
        时序 RAG：获取截至当前章节的最相关角色档案。
        逻辑：查询所有 chapter <= current_chapter_idx 的记录，并合并。
        """
        store = self.get_store(name)
        # Chroma 过滤器
        results = store.get(
            where={"chapter": {"$lte": current_chapter_idx}}
        )
        
        if not results or not results["documents"]:
            return {}
            
        # 合并策略：按章节顺序合并描述，后出现的覆盖/补充旧的
        merged_profile = {}
        # 注意：store.get 返回的记录顺序可能不确定，我们需要手动按 chapter 排序
        docs = results["documents"]
        metas = results["metadatas"]
        
        indexed_docs = sorted(zip(metas, docs), key=lambda x: x[0]["chapter"])
        
        for meta, doc in indexed_docs:
            try:
                trait = json.loads(doc)
                merged_profile.update(trait)
            except json.JSONDecodeError:
                continue
                
        return merged_profile
