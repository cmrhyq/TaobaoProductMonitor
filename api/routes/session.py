"""
Login session endpoints.

淘宝强制登录，而扫码必须有头浏览器，因此登录端点是**阻塞**的：请求会一直等待，
直到扫码成功或超时。FastAPI 对同步 `def` 端点会自动丢到线程池执行，不会阻塞事件循环。

无桌面环境（容器 / 远程服务器）无法弹出浏览器窗口，此时应在本机执行
`python -m tbmon login` 生成登录态文件，再让服务读取。
"""


import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config.settings import get_settings
from task.task import is_running
from tbmon import ItemService
from tbmon.errors import AuthRequiredError, TbMonError
from tbmon.models import StateStatus
from tbmon.session import validate_state

logger = structlog.get_logger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """扫码登录参数。"""

    timeout_s: int | None = Field(
        default=None, ge=10, le=900, description="等待扫码的秒数，默认取 TB_LOGIN_TIMEOUT_S"
    )


class SessionStateResponse(BaseModel):
    """登录态体检结果。"""

    ok: bool
    exists: bool
    reason: str
    storage_state: str
    cookie_count: int = 0
    has_login_cookie: bool = False
    age_days: float | None = None
    expires_in_days: float | None = None


def _to_response(status: StateStatus, storage_state: str) -> SessionStateResponse:
    return SessionStateResponse(
        ok=status.ok,
        exists=status.exists,
        reason=status.reason,
        storage_state=storage_state,
        cookie_count=status.cookie_count or 0,
        has_login_cookie=bool(status.has_login_cookie),
        age_days=status.age_days,
        expires_in_days=status.expires_in_days,
    )


def _event_collector(sink: list[str]):
    """把登录过程中的提示同时收进响应体与日志。"""

    def on_event(message: str) -> None:
        sink.append(message)
        logger.info("login progress", message=message)

    return on_event


@router.get("/state", response_model=SessionStateResponse)
def session_state():
    """体检登录态：只读检查文件与 cookie，不启动浏览器。"""
    fetch = get_settings().fetch
    status = validate_state(fetch.storage_state, stale_days=fetch.state_stale_days)
    return _to_response(status, str(fetch.storage_state))


@router.post("/login", response_model=dict)
def session_login(body: LoginRequest | None = None):
    """拉起有头浏览器扫码登录，成功后将登录态落盘。请求会阻塞至成功或超时。"""
    settings = get_settings()
    if is_running():
        # 浏览器资源互斥：登录与监控轮次不能同时开两个 Chromium
        raise HTTPException(status_code=409, detail="监控轮次正在执行，请稍后再试")

    timeout_s = (body.timeout_s if body else None) or settings.fetch.login_timeout_s
    logs: list[str] = []
    logger.info("Scan-to-login requested", timeout_s=timeout_s)

    try:
        # 在本请求线程内创建并关闭：Playwright 同步对象不可跨线程使用
        with ItemService(settings.fetch) as service:
            path = service.login(timeout_s=timeout_s, on_event=_event_collector(logs))
            status = service.login_state()
    except AuthRequiredError as exc:
        raise HTTPException(
            status_code=408, detail={"message": str(exc), "logs": logs}
        ) from exc
    except TbMonError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(exc),
                "logs": logs,
                "hint": "若服务运行在无桌面环境，请在本机执行 python -m tbmon login 后复制登录态文件",
            },
        ) from exc

    return {
        "ok": status.ok,
        "reason": status.reason,
        "storage_state": str(path),
        "state": _to_response(status, str(settings.fetch.storage_state)).model_dump(),
        "logs": logs,
    }
