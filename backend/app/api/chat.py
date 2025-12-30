from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json
from app.database import get_db
from app.services.ai_service import ai_service
from app.services.vector_service import vector_service
from app.models.conversation import Conversation
from sqlalchemy import select, desc, delete

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_rag: bool = True


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """与AI对话"""
    session_id = request.session_id or str(uuid.uuid4())

    response = await ai_service.chat(
        db=db,
        session_id=session_id,
        user_message=request.message,
        use_rag=request.use_rag
    )

    return {
        "session_id": session_id,
        "response": response
    }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """流式对话"""
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        async for chunk in ai_service.chat_stream(
            db=db,
            session_id=session_id,
            user_message=request.message,
            use_rag=request.use_rag
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/history")
async def get_chat_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """获取对话历史"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.created_at)
        .limit(limit)
    )
    conversations = result.scalars().all()

    return {
        "session_id": session_id,
        "messages": [c.to_dict() for c in conversations]
    }


@router.delete("/history")
async def clear_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """清除对话历史"""
    await db.execute(
        delete(Conversation).where(Conversation.session_id == session_id)
    )
    await db.commit()

    return {"message": "对话历史已清除"}


@router.get("/sessions")
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    """获取所有会话列表"""
    result = await db.execute(
        select(Conversation.session_id, Conversation.created_at)
        .group_by(Conversation.session_id, Conversation.created_at)
        .order_by(desc(Conversation.created_at))
        .limit(limit)
    )
    sessions = result.all()

    return {
        "sessions": [
            {"session_id": s[0], "created_at": s[1].isoformat() if s[1] else None}
            for s in sessions
        ]
    }


@router.post("/search")
async def search_emails(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """语义搜索邮件"""
    results = await vector_service.search_similar(
        db=db,
        query=request.query,
        top_k=request.top_k
    )

    return {
        "query": request.query,
        "results": [
            {
                "email": email.to_dict(),
                "similarity": similarity,
                "matched_content": chunk
            }
            for email, similarity, chunk in results
        ]
    }


@router.post("/summarize")
async def summarize_emails(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db)
):
    """总结近期邮件"""
    summary = await ai_service.summarize_emails(db=db, days=days)
    return {"summary": summary}
