import logging
import httpx
from typing import List, Optional, Tuple
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.config import settings
from app.models.email import Email, EmailVector

logger = logging.getLogger(__name__)


class VectorService:
    """向量化服务 - 使用硅基流动免费Embedding API"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 硅基流动免费embedding API（可选配置）
        self.embedding_api_url = "https://api.siliconflow.cn/v1/embeddings"
        self.embedding_api_key = settings.embedding_api_key if hasattr(settings, 'embedding_api_key') else ""
        self.embedding_model = "BAAI/bge-large-zh-v1.5"
        self._use_api = bool(self.embedding_api_key)

        if not self._use_api:
            logger.info("未配置Embedding API，将使用关键词搜索模式")
        else:
            logger.info("使用硅基流动Embedding API")

    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """将文本分块"""
        if not text:
            return []

        chunk_size = chunk_size or settings.chunk_size
        overlap = overlap or settings.chunk_overlap

        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        if not chunks and text:
            for i in range(0, len(text), chunk_size - overlap):
                chunk = text[i:i + chunk_size]
                if chunk:
                    chunks.append(chunk)

        return chunks

    def embed_text_sync(self, text: str) -> Optional[List[float]]:
        """同步方式将文本转换为向量"""
        if not text or not self._use_api:
            return None
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    self.embedding_api_url,
                    headers={
                        "Authorization": f"Bearer {self.embedding_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.embedding_model,
                        "input": text[:2000]  # 限制长度
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"向量化失败: {e}")
        return None

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """异步方式将文本转换为向量"""
        if not text or not self._use_api:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.embedding_api_url,
                    headers={
                        "Authorization": f"Bearer {self.embedding_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.embedding_model,
                        "input": text[:2000]
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"向量化失败: {e}")
        return None

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        if not texts or not self._use_api:
            return []

        embeddings = []
        for text in texts:
            emb = await self.embed_text(text)
            if emb:
                embeddings.append(emb)
        return embeddings

    async def vectorize_email(self, db: AsyncSession, email_id: int) -> bool:
        """向量化单封邮件"""
        try:
            result = await db.execute(select(Email).where(Email.id == email_id))
            email_obj = result.scalar_one_or_none()

            if not email_obj:
                return False

            # 删除旧的向量
            await db.execute(
                text("DELETE FROM email_vectors WHERE email_id = :email_id"),
                {"email_id": email_id}
            )

            # 构建文本
            full_text = f"主题: {email_obj.subject or ''}\n"
            full_text += f"发件人: {email_obj.sender or ''}\n"
            full_text += f"日期: {email_obj.date.strftime('%Y-%m-%d %H:%M') if email_obj.date else ''}\n\n"
            full_text += email_obj.body_text or ""

            # 分块
            chunks = self.chunk_text(full_text)
            if not chunks:
                chunks = [full_text[:settings.chunk_size]]

            # 存储分块（向量可选）
            for idx, chunk in enumerate(chunks):
                embedding = await self.embed_text(chunk) if self._use_api else None
                vector = EmailVector(
                    email_id=email_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=embedding
                )
                db.add(vector)

            await db.commit()
            logger.info(f"邮件 {email_id} 处理完成，共 {len(chunks)} 个分块")
            return True

        except Exception as e:
            logger.error(f"处理邮件 {email_id} 失败: {e}")
            await db.rollback()
            return False

    async def vectorize_all_emails(self, db: AsyncSession) -> dict:
        """处理所有未处理的邮件"""
        try:
            result = await db.execute(
                text("""
                    SELECT e.id FROM emails e
                    LEFT JOIN email_vectors ev ON e.id = ev.email_id
                    WHERE ev.id IS NULL
                """)
            )
            email_ids = [row[0] for row in result.fetchall()]

            success_count = 0
            for email_id in email_ids:
                if await self.vectorize_email(db, email_id):
                    success_count += 1

            return {
                "total": len(email_ids),
                "success": success_count,
                "failed": len(email_ids) - success_count
            }

        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            return {"error": str(e)}

    async def search_similar(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[Tuple[Email, float, str]]:
        """搜索相关邮件 - 向量搜索或关键词搜索"""
        try:
            # 如果有向量API，使用向量搜索
            if self._use_api:
                query_embedding = await self.embed_text(query)
                if query_embedding:
                    return await self._vector_search(db, query_embedding, top_k, threshold)

            # 否则使用关键词搜索
            return await self._keyword_search(db, query, top_k)

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    async def _vector_search(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        top_k: int,
        threshold: float
    ) -> List[Tuple[Email, float, str]]:
        """向量相似度搜索"""
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        result = await db.execute(
            text("""
                SELECT
                    ev.email_id,
                    ev.chunk_text,
                    1 - (ev.embedding <=> :embedding::vector) as similarity
                FROM email_vectors ev
                WHERE ev.embedding IS NOT NULL
                  AND 1 - (ev.embedding <=> :embedding::vector) > :threshold
                ORDER BY ev.embedding <=> :embedding::vector
                LIMIT :limit
            """),
            {
                "embedding": embedding_str,
                "threshold": threshold,
                "limit": top_k * 2
            }
        )

        rows = result.fetchall()
        results = []
        seen_emails = set()

        for email_id, chunk_text, similarity in rows:
            if email_id in seen_emails:
                continue
            seen_emails.add(email_id)

            email_result = await db.execute(
                select(Email).where(Email.id == email_id)
            )
            email_obj = email_result.scalar_one_or_none()
            if email_obj:
                results.append((email_obj, float(similarity), chunk_text))

            if len(results) >= top_k:
                break

        return results

    async def _keyword_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int
    ) -> List[Tuple[Email, float, str]]:
        """关键词搜索"""
        # 提取关键词
        keywords = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not keywords:
            keywords = [query]

        # 构建搜索条件
        conditions = []
        params = {}
        for i, kw in enumerate(keywords[:5]):  # 最多5个关键词
            param_name = f"kw{i}"
            conditions.append(f"(ev.chunk_text ILIKE :{param_name})")
            params[param_name] = f"%{kw}%"

        where_clause = " OR ".join(conditions) if conditions else "1=1"

        result = await db.execute(
            text(f"""
                SELECT DISTINCT ON (ev.email_id)
                    ev.email_id,
                    ev.chunk_text,
                    1.0 as similarity
                FROM email_vectors ev
                WHERE {where_clause}
                ORDER BY ev.email_id, ev.chunk_index
                LIMIT :limit
            """),
            {**params, "limit": top_k}
        )

        rows = result.fetchall()
        results = []

        for email_id, chunk_text, similarity in rows:
            email_result = await db.execute(
                select(Email).where(Email.id == email_id)
            )
            email_obj = email_result.scalar_one_or_none()
            if email_obj:
                results.append((email_obj, float(similarity), chunk_text))

        return results


# 全局实例
vector_service = VectorService()
