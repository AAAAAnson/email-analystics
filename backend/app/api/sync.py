from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.sync_status import SyncStatus
from app.services.email_service import email_service
from app.services.vector_service import vector_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


async def sync_and_vectorize(db: AsyncSession, folder: str):
    """同步邮件并向量化"""
    # 同步邮件
    result = await email_service.sync_emails_to_db(db, folder=folder)

    if result.get("success"):
        # 向量化新邮件
        await vector_service.vectorize_all_emails(db)

    return result


@router.post("/emails")
async def sync_emails(
    background_tasks: BackgroundTasks,
    folder: str = "INBOX",
    db: AsyncSession = Depends(get_db)
):
    """手动触发邮件同步"""
    # 检查是否正在同步
    result = await db.execute(
        select(SyncStatus).where(SyncStatus.folder == folder)
    )
    status = result.scalar_one_or_none()

    if status and status.status == "syncing":
        return {"message": "正在同步中，请稍候"}

    # 同步邮件
    sync_result = await email_service.sync_emails_to_db(db, folder=folder)

    if sync_result.get("success"):
        # 向量化
        vector_result = await vector_service.vectorize_all_emails(db)
        sync_result["vectorization"] = vector_result

    return sync_result


@router.get("/status")
async def get_sync_status(
    folder: str = "INBOX",
    db: AsyncSession = Depends(get_db)
):
    """获取同步状态"""
    result = await db.execute(
        select(SyncStatus).where(SyncStatus.folder == folder)
    )
    status = result.scalar_one_or_none()

    if not status:
        return {
            "folder": folder,
            "status": "not_started",
            "total_emails": 0,
            "last_sync_at": None
        }

    return status.to_dict()


@router.post("/vectorize")
async def vectorize_emails(
    db: AsyncSession = Depends(get_db)
):
    """手动触发向量化"""
    result = await vector_service.vectorize_all_emails(db)
    return result


@router.get("/vector-stats")
async def get_vector_stats(
    db: AsyncSession = Depends(get_db)
):
    """获取向量化统计"""
    from sqlalchemy import text

    # 总邮件数
    total_emails = (await db.execute(text("SELECT COUNT(*) FROM emails"))).scalar()

    # 已向量化邮件数
    vectorized = (await db.execute(
        text("SELECT COUNT(DISTINCT email_id) FROM email_vectors")
    )).scalar()

    # 向量块数
    total_chunks = (await db.execute(
        text("SELECT COUNT(*) FROM email_vectors")
    )).scalar()

    return {
        "total_emails": total_emails,
        "vectorized_emails": vectorized,
        "pending_emails": total_emails - vectorized,
        "total_chunks": total_chunks
    }
