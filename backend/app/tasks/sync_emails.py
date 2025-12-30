import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.database import async_session
from app.services.email_service import EmailService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


def run_async(coro):
    """在同步环境中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def sync_emails_task(self, folder: str = "INBOX", full_sync: bool = False):
    """同步邮件任务"""
    logger.info(f"开始同步邮件: folder={folder}, full_sync={full_sync}")

    async def _sync():
        async with async_session() as db:
            email_service = EmailService()
            vector_service = VectorService()

            # 同步邮件
            limit = 1000 if full_sync else 100
            result = await email_service.sync_emails_to_db(db, folder=folder, limit=limit)

            if result.get("success"):
                # 向量化新邮件
                vector_result = await vector_service.vectorize_all_emails(db)
                result["vectorization"] = vector_result
                logger.info(f"同步完成: {result}")
            else:
                logger.error(f"同步失败: {result}")

            return result

    try:
        return run_async(_sync())
    except Exception as e:
        logger.error(f"同步任务失败: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def check_new_emails_task(self):
    """检查新邮件任务"""
    logger.info("检查新邮件...")

    async def _check():
        async with async_session() as db:
            email_service = EmailService()
            vector_service = VectorService()

            # 只获取最新的邮件
            result = await email_service.sync_emails_to_db(db, folder="INBOX", limit=50)

            if result.get("success") and result.get("new_emails", 0) > 0:
                # 向量化新邮件
                await vector_service.vectorize_all_emails(db)
                logger.info(f"发现 {result['new_emails']} 封新邮件")

                # TODO: 发送WebSocket通知
                return {
                    "new_emails": result["new_emails"],
                    "notified": True
                }

            return {"new_emails": 0}

    try:
        return run_async(_check())
    except Exception as e:
        logger.error(f"检查新邮件失败: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task
def vectorize_email_task(email_id: int):
    """向量化单封邮件"""
    async def _vectorize():
        async with async_session() as db:
            vector_service = VectorService()
            return await vector_service.vectorize_email(db, email_id)

    return run_async(_vectorize())
