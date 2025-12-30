from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import emails_router, chat_router, sync_router
from app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("邮件智能助手启动中...")
    logger.info(f"邮箱: {settings.email_address}")
    logger.info(f"IMAP服务器: {settings.email_imap_server}")
    yield
    logger.info("邮件智能助手已关闭")


app = FastAPI(
    title="邮件智能助手",
    description="基于RAG的智能邮件管理助手，使用DeepSeek AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(emails_router)
app.include_router(chat_router)
app.include_router(sync_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "邮件智能助手",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/api/config")
async def get_config():
    """获取公开配置"""
    return {
        "email_address": settings.email_address,
        "imap_server": settings.email_imap_server,
        "embedding_model": settings.embedding_model
    }
