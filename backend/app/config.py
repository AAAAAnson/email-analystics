from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 邮箱配置
    email_address: str = ""
    email_password: str = ""
    email_imap_server: str = "imap.163.com"
    email_imap_port: int = 993
    email_smtp_server: str = "smtp.163.com"
    email_smtp_port: int = 465

    # Gemini API配置 (使用OpenAI兼容格式)
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.0-flash-exp"  # 或 gemini-1.5-flash, gemini-1.5-pro

    # 数据库配置
    database_url: str = "postgresql://emailbot:emailbot123@localhost:5432/emailbot"

    # Redis配置
    redis_url: str = "redis://localhost:6379/0"

    # 服务配置
    backend_port: int = 9090
    websocket_port: int = 9092

    # 向量化配置 (可选：配置硅基流动API实现语义搜索)
    embedding_api_key: str = ""  # 硅基流动API Key，可在 https://siliconflow.cn 免费获取
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_dimension: int = 1024
    chunk_size: int = 500
    chunk_overlap: int = 50

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
