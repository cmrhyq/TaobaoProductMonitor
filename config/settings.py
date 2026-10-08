"""
Application settings and configuration management.
Uses pydantic-settings for environment variable loading and validation.

唯一运行时配置入口，聚合五组配置：
    app      APP_NAME / LOG_LEVEL / DEBUG
    db       DB_*
    mail     MAIL_*
    monitor  MONITOR_*      （服务内嵌调度器）
    fetch    TB_*           （抓取参数，由 tbmon.config.Settings 提供）
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 抓取参数（TB_ 前缀）的唯一来源；tbmon 包自带 Settings，这里只是组合进主配置
from tbmon.config import Settings as FetchSettings

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


class MonitorSettings(BaseSettings):
    """监控调度配置（服务内嵌调度器）"""
    model_config = SettingsConfigDict(
        env_prefix="MONITOR_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    schedule_enabled: bool = Field(default=True, description="是否随服务启动内置定时监控")
    interval_minutes: int = Field(default=60, ge=1, description="监控轮次间隔（分钟）")
    run_on_startup: bool = Field(default=False, description="服务启动后是否立即跑一轮")


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
        self.monitor = MonitorSettings()
        self.mail = MailSettings()
        self.app = AppSettings()

        # 抓取参数统一由 tbmon 提供（TB_ 前缀），此处解析为项目根下的绝对路径，
        # 避免进程 CWD 变化导致登录态文件找不到。
        self.fetch = FetchSettings(_env_file=ENV_FILE_PATH)
        if not self.fetch.storage_state.is_absolute():
            self.fetch.storage_state = PROJECT_ROOT / self.fetch.storage_state

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

    def get_db_path(self) -> str:
        if self.db.type == "sqlite":
            path = Path(self.db.sqlite_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return str(path)
        return ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton instance."""
    return Settings()
