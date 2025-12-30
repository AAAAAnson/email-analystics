import logging
import re
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.config import settings
from app.models.conversation import Conversation
from app.models.email import Email
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=60.0,  # 增加超时时间
            max_retries=2
        )
        self.model = "deepseek-chat"

    def _build_system_prompt(self, context_emails: List[tuple] = None, has_emails: bool = False) -> str:
        """构建系统提示词"""
        base_prompt = """你是一个智能邮件助手，专门帮助用户管理和查询邮件内容。

【重要规则 - 必须严格遵守】
1. 你只能基于下方提供的【邮件内容】来回答问题
2. 绝对禁止编造、虚构任何邮件内容、发件人、主题或日期
3. 如果下方没有提供邮件内容，或者提供的邮件与用户问题无关，必须回复："抱歉，我没有找到相关的邮件信息。请尝试用其他关键词描述您要查找的内容。"
4. 引用邮件时必须准确标注：发件人、主题、日期

"""
        if context_emails and len(context_emails) > 0:
            base_prompt += f"\n以下是系统检索到的 {len(context_emails)} 封相关邮件：\n"
            base_prompt += "=" * 50 + "\n"
            for email_obj, similarity, chunk in context_emails:
                base_prompt += f"\n【邮件 ID:{email_obj.id}】\n"
                base_prompt += f"发件人: {email_obj.sender}\n"
                base_prompt += f"主题: {email_obj.subject}\n"
                base_prompt += f"日期: {email_obj.date.strftime('%Y-%m-%d %H:%M') if email_obj.date else '未知'}\n"
                base_prompt += f"内容摘要:\n{chunk}\n"
                if email_obj.body_text and len(email_obj.body_text) > len(chunk):
                    # 如果有更多内容，也提供
                    full_content = email_obj.body_text[:1500]
                    base_prompt += f"\n完整内容:\n{full_content}\n"
                base_prompt += "-" * 30 + "\n"
            base_prompt += "=" * 50 + "\n"
        else:
            base_prompt += "\n【注意】系统未检索到相关邮件。请如实告知用户。\n"

        return base_prompt

    def _is_latest_email_query(self, query: str) -> bool:
        """判断是否是查询最新邮件"""
        patterns = [
            r'最新', r'最近', r'刚[收到|来]', r'今天', r'昨天',
            r'newest', r'latest', r'recent', r'last'
        ]
        return any(re.search(p, query.lower()) for p in patterns)

    async def _get_latest_emails(self, db: AsyncSession, limit: int = 5) -> List[Email]:
        """获取最新的邮件"""
        result = await db.execute(
            select(Email)
            .order_by(desc(Email.date))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_conversation_history(
        self,
        db: AsyncSession,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """获取对话历史"""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        conversations = result.scalars().all()
        conversations = list(reversed(conversations))

        return [
            {"role": conv.role, "content": conv.content}
            for conv in conversations
        ]

    async def save_conversation(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        related_emails: List[int] = None
    ):
        """保存对话记录"""
        conv = Conversation(
            session_id=session_id,
            role=role,
            content=content,
            related_emails=related_emails or []
        )
        db.add(conv)
        await db.commit()

    async def chat(
        self,
        db: AsyncSession,
        session_id: str,
        user_message: str,
        use_rag: bool = True
    ) -> str:
        """与AI对话"""
        try:
            context_emails = []
            related_email_ids = []

            # 判断是否查询最新邮件
            if self._is_latest_email_query(user_message):
                # 直接获取最新邮件
                latest_emails = await self._get_latest_emails(db, limit=5)
                context_emails = [
                    (email, 1.0, email.body_text[:500] if email.body_text else "")
                    for email in latest_emails
                ]
                related_email_ids = [e.id for e in latest_emails]
            elif use_rag:
                # 使用向量/关键词搜索
                context_emails = await vector_service.search_similar(
                    db, user_message, top_k=5, threshold=0.3
                )
                related_email_ids = [e[0].id for e in context_emails]

                # 如果没找到相关邮件，获取最新的几封作为参考
                if not context_emails:
                    latest_emails = await self._get_latest_emails(db, limit=3)
                    if latest_emails:
                        context_emails = [
                            (email, 0.5, email.body_text[:500] if email.body_text else "")
                            for email in latest_emails
                        ]
                        related_email_ids = [e.id for e in latest_emails]

            # 构建系统提示词
            system_prompt = self._build_system_prompt(context_emails, has_emails=len(context_emails) > 0)

            # 获取对话历史
            history = await self.get_conversation_history(db, session_id)

            # 构建消息
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            # 调用DeepSeek API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # 降低随机性，减少编造
                max_tokens=2000
            )

            assistant_message = response.choices[0].message.content

            # 保存对话
            await self.save_conversation(db, session_id, "user", user_message, related_email_ids)
            await self.save_conversation(db, session_id, "assistant", assistant_message)

            return assistant_message

        except Exception as e:
            logger.error(f"AI对话失败: {e}")
            return f"抱歉，处理您的问题时出现错误: {str(e)}"

    async def chat_stream(
        self,
        db: AsyncSession,
        session_id: str,
        user_message: str,
        use_rag: bool = True
    ) -> AsyncGenerator[str, None]:
        """流式对话"""
        try:
            context_emails = []
            related_email_ids = []

            # 判断是否查询最新邮件
            if self._is_latest_email_query(user_message):
                latest_emails = await self._get_latest_emails(db, limit=5)
                context_emails = [
                    (email, 1.0, email.body_text[:500] if email.body_text else "")
                    for email in latest_emails
                ]
                related_email_ids = [e.id for e in latest_emails]
            elif use_rag:
                context_emails = await vector_service.search_similar(
                    db, user_message, top_k=5, threshold=0.3
                )
                related_email_ids = [e[0].id for e in context_emails]

                if not context_emails:
                    latest_emails = await self._get_latest_emails(db, limit=3)
                    if latest_emails:
                        context_emails = [
                            (email, 0.5, email.body_text[:500] if email.body_text else "")
                            for email in latest_emails
                        ]
                        related_email_ids = [e.id for e in latest_emails]

            # 构建系统提示词
            system_prompt = self._build_system_prompt(context_emails, has_emails=len(context_emails) > 0)

            # 获取对话历史
            history = await self.get_conversation_history(db, session_id)

            # 构建消息
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            # 调用DeepSeek API (流式)
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                stream=True
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

            # 保存对话
            await self.save_conversation(db, session_id, "user", user_message, related_email_ids)
            await self.save_conversation(db, session_id, "assistant", full_response)

        except Exception as e:
            logger.error(f"AI流式对话失败: {e}")
            yield f"抱歉，处理您的问题时出现错误: {str(e)}"

    async def summarize_emails(
        self,
        db: AsyncSession,
        email_ids: List[int] = None,
        days: int = 7
    ) -> str:
        """总结邮件"""
        try:
            if email_ids:
                result = await db.execute(
                    select(Email).where(Email.id.in_(email_ids))
                )
            else:
                from datetime import datetime, timedelta
                since_date = datetime.utcnow() - timedelta(days=days)
                result = await db.execute(
                    select(Email)
                    .where(Email.date >= since_date)
                    .order_by(desc(Email.date))
                    .limit(50)
                )

            emails = result.scalars().all()

            if not emails:
                return "没有找到需要总结的邮件。"

            # 构建邮件摘要
            email_summaries = []
            for e in emails:
                summary = f"- 主题: {e.subject}\n  发件人: {e.sender}\n  日期: {e.date.strftime('%Y-%m-%d') if e.date else '未知'}"
                email_summaries.append(summary)

            prompt = f"""请总结以下 {len(emails)} 封邮件的主要内容和重点：

{chr(10).join(email_summaries)}

请提供：
1. 整体概述（主要涉及哪些方面）
2. 重要邮件提醒（需要关注或回复的）
3. 待办事项（如果有提到的话）"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个邮件助手，帮助用户总结和分析邮件。只基于提供的信息回答，不要编造。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"邮件总结失败: {e}")
            return f"总结邮件时出现错误: {str(e)}"


# 全局实例
ai_service = AIService()
