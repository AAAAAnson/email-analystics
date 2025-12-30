from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "email_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sync_emails"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10分钟超时
    worker_prefetch_multiplier=1,
)

# 定时任务配置
celery_app.conf.beat_schedule = {
    # 每5分钟检查新邮件
    "check-new-emails": {
        "task": "app.tasks.sync_emails.check_new_emails_task",
        "schedule": 300.0,  # 5分钟
    },
    # 每天凌晨2点全量同步
    "daily-full-sync": {
        "task": "app.tasks.sync_emails.sync_emails_task",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"full_sync": True}
    },
}
