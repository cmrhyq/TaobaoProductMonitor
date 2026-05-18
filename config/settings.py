"""
Application settings and configuration management.
Uses pydantic-settings for environment variable loading and validation.
"""

from pathlib import Path
from typing import Optional
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE_PATH)


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(
        env_prefix="DB_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    type: str = Field(default="sqlite", description="数据库类型: sqlite/mysql")
    sqlite_path: str = Field(default="db/ProductMonitor.db")
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(default="")
    mysql_database: str = Field(default="product_monitor")


class TaobaoApiSettings(BaseSettings):
    """淘宝 H5 API 配置"""
    model_config = SettingsConfigDict(
        env_prefix="TAOBAO_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    app_key: str = Field(default="12574478")
    request_interval: float = Field(default=3.0, ge=1.0, le=10.0, description="请求间隔秒数")
    max_retries: int = Field(default=3, ge=1, le=10, description="最大重试次数")
    timeout: int = Field(default=10, ge=5, le=60, description="请求超时秒数")


class ProxySettings(BaseSettings):
    """代理配置"""
    model_config = SettingsConfigDict(
        env_prefix="PROXY_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    enabled: bool = Field(default=False, description="是否启用代理")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=7890)

    @property
    def url(self) -> Optional[str]:
        if self.enabled:
            return f"http://{self.host}:{self.port}"
        return None


class PlaywrightSettings(BaseSettings):
    """Playwright 回退配置"""
    model_config = SettingsConfigDict(
        env_prefix="PLAYWRIGHT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    headless: bool = Field(default=True, description="是否无头模式")
    timeout: int = Field(default=30000, description="页面加载超时毫秒")
    slow_mo: int = Field(default=0, description="操作延迟毫秒")


class MailSettings(BaseSettings):
    """邮件配置"""
    model_config = SettingsConfigDict(
        env_prefix="MAIL_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    host: str = Field(default="smtp.163.com")
    port: int = Field(default=25)
    sender: str = Field(default="")
    license_key: str = Field(default="", description="邮箱授权码")


class AppSettings(BaseSettings):
    """应用级配置"""
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    app_name: str = Field(default="TaobaoProductMonitor")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)


class Settings:
    """聚合所有配置的主入口"""

    def __init__(self):
        self.db = DatabaseSettings()
        self.taobao_api = TaobaoApiSettings()
        self.proxy = ProxySettings()
        self.playwright = PlaywrightSettings()
        self.mail = MailSettings()
        self.app = AppSettings()

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy-compatible database URL."""
        if self.db.type == "sqlite":
            path = Path(self.db.sqlite_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return f"sqlite:///{path}"
        return (
            f"mysql+pymysql://{self.db.mysql_user}:{self.db.mysql_password}"
            f"@{self.db.mysql_host}:{self.db.mysql_port}/{self.db.mysql_database}"
            f"?charset=utf8mb4"
        )

    def get_proxy_url(self) -> Optional[str]:
        return self.proxy.url

    def get_db_path(self) -> str:
        if self.db.type == "sqlite":
            path = Path(self.db.sqlite_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return str(path)
        return ""


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings singleton instance."""
    return Settings()
