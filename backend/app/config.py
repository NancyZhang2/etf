"""
应用配置 — 从环境变量或 .env 文件加载
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    """应用配置，全部从环境变量读取"""

    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://etf_user:password@localhost:5432/etf_quant",
    )

    # Claude API
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")

    # 微信公众号
    WECHAT_APPID: str = os.getenv("WECHAT_APPID", "")
    WECHAT_APPSECRET: str = os.getenv("WECHAT_APPSECRET", "")
    WECHAT_TOKEN: str = os.getenv("WECHAT_TOKEN", "")

    # SMTP 邮件
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    # 应用
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    WEB_MANAGER_PORT: int = int(os.getenv("WEB_MANAGER_PORT", "8080"))

    # 备份
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "/data/etf/backups")


settings = Settings()
