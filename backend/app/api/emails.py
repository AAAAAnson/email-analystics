from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List
from app.database import get_db
from app.models.email import Email

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
async def get_emails(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    folder: str = Query("INBOX"),
    search: Optional[str] = None,
    sender: Optional[str] = None
):
    """获取邮件列表"""
    query = select(Email).where(Email.folder == folder)

    if search:
        query = query.where(
            Email.subject.ilike(f"%{search}%") |
            Email.body_text.ilike(f"%{search}%")
        )

    if sender:
        query = query.where(Email.sender.ilike(f"%{sender}%"))

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页
    query = query.order_by(desc(Email.date))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    emails = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "emails": [e.to_dict() for e in emails]
    }


@router.get("/stats")
async def get_email_stats(db: AsyncSession = Depends(get_db)):
    """获取邮件统计"""
    # 总邮件数
    total = (await db.execute(select(func.count(Email.id)))).scalar()

    # 未读邮件数
    unread = (await db.execute(
        select(func.count(Email.id)).where(Email.is_read == False)
    )).scalar()

    # 有附件的邮件数
    with_attachments = (await db.execute(
        select(func.count(Email.id)).where(Email.has_attachments == True)
    )).scalar()

    # 按发件人统计Top10
    top_senders = (await db.execute(
        select(Email.sender, func.count(Email.id).label("count"))
        .group_by(Email.sender)
        .order_by(desc("count"))
        .limit(10)
    )).all()

    return {
        "total": total,
        "unread": unread,
        "with_attachments": with_attachments,
        "top_senders": [{"sender": s, "count": c} for s, c in top_senders]
    }


@router.get("/{email_id}")
async def get_email_detail(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取邮件详情"""
    result = await db.execute(select(Email).where(Email.id == email_id))
    email_obj = result.scalar_one_or_none()

    if not email_obj:
        raise HTTPException(status_code=404, detail="邮件不存在")

    # 标记为已读
    if not email_obj.is_read:
        email_obj.is_read = True
        await db.commit()

    return email_obj.to_dict()


@router.delete("/{email_id}")
async def delete_email(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除邮件（仅从数据库删除）"""
    result = await db.execute(select(Email).where(Email.id == email_id))
    email_obj = result.scalar_one_or_none()

    if not email_obj:
        raise HTTPException(status_code=404, detail="邮件不存在")

    await db.delete(email_obj)
    await db.commit()

    return {"message": "邮件已删除"}


@router.post("/{email_id}/read")
async def mark_as_read(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """标记邮件为已读"""
    result = await db.execute(select(Email).where(Email.id == email_id))
    email_obj = result.scalar_one_or_none()

    if not email_obj:
        raise HTTPException(status_code=404, detail="邮件不存在")

    email_obj.is_read = True
    await db.commit()

    return {"message": "已标记为已读"}
