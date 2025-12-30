import logging
from typing import List, Optional, Tuple
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.models.email import Email, EmailVector

logger = logging.getLogger(__name__)


class VectorService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            logger.info(f"加载Embedding模型: {settings.embedding_model}")
            try:
                self._model = SentenceTransformer(settings.embedding_model)
                logger.info("Embedding模型加载成功")
            except Exception as e:
                logger.error(f"加载Embedding模型失败: {e}")
                # 使用备用小模型
                self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """将文本分块"""
        if not text:
            return []

        chunk_size = chunk_size or settings.chunk_size
        overlap = overlap or settings.chunk_overlap

        # 按段落分割
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

        # 如果没有分出块，按字符分割
        if not chunks and text:
            for i in range(0, len(text), chunk_size - overlap):
                chunk = text[i:i + chunk_size]
                if chunk:
                    chunks.append(chunk)

        return chunks

    def embed_text(self, text: str) -> Optional[List[float]]:
        """将文本转换为向量"""
        if not text or not self._model:
            return None
        try:
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            return None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        if not texts or not self._model:
            return []
        try:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"批量向量化失败: {e}")
            return []

    async def vectorize_email(self, db: AsyncSession, email_id: int) -> bool:
        """向量化单封邮件"""
        try:
            # 获取邮件
            result = await db.execute(select(Email).where(Email.id == email_id))
            email_obj = result.scalar_one_or_none()

            if not email_obj:
                return False

            # 删除旧的向量
            await db.execute(
                text("DELETE FROM email_vectors WHERE email_id = :email_id"),
                {"email_id": email_id}
            )

            # 构建要向量化的文本
            full_text = f"主题: {email_obj.subject or ''}\n"
            full_text += f"发件人: {email_obj.sender or ''}\n"
            full_text += f"日期: {email_obj.date.strftime('%Y-%m-%d %H:%M') if email_obj.date else ''}\n\n"
            full_text += email_obj.body_text or ""

            # 分块
            chunks = self.chunk_text(full_text)
            if not chunks:
                chunks = [full_text[:settings.chunk_size]]

            # 向量化并存储
            embeddings = self.embed_texts(chunks)

            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector = EmailVector(
                    email_id=email_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=embedding
                )
                db.add(vector)

            await db.commit()
            logger.info(f"邮件 {email_id} 向量化完成，共 {len(chunks)} 个分块")
            return True

        except Exception as e:
            logger.error(f"向量化邮件 {email_id} 失败: {e}")
            await db.rollback()
            return False

    async def vectorize_all_emails(self, db: AsyncSession) -> dict:
        """向量化所有未向量化的邮件"""
        try:
            # 找出未向量化的邮件
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
            logger.error(f"批量向量化失败: {e}")
            return {"error": str(e)}

    async def search_similar(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[Tuple[Email, float, str]]:
        """搜索相似邮件"""
        try:
            # 向量化查询
            query_embedding = self.embed_text(query)
            if not query_embedding:
                return []

            # 使用pgvector进行相似度搜索
            embedding_str = f"[{','.join(map(str, query_embedding))}]"
            result = await db.execute(
                text("""
                    SELECT
                        ev.email_id,
                        ev.chunk_text,
                        1 - (ev.embedding <=> :embedding::vector) as similarity
                    FROM email_vectors ev
                    WHERE 1 - (ev.embedding <=> :embedding::vector) > :threshold
                    ORDER BY ev.embedding <=> :embedding::vector
                    LIMIT :limit
                """),
                {
                    "embedding": embedding_str,
                    "threshold": threshold,
                    "limit": top_k
                }
            )

            rows = result.fetchall()

            # 获取完整邮件信息
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

            return results

        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []


# 全局实例
vector_service = VectorService()
